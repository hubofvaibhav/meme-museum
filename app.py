from urllib import response
from config import AWS_ACCESS_KEY, AWS_SECRET_KEY, REGION, S3_BUCKET
from flask import Flask, render_template, request, redirect, session
import boto3
import uuid
from passlib.hash import pbkdf2_sha256
from config import *
from boto3.dynamodb.conditions import Attr
from datetime import datetime
from flask import flash
import json


app = Flask(__name__)
app.secret_key = "meme_secret_key"
lambda_client = boto3.client(
    'lambda',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION
)


# AWS Connections
dynamodb = boto3.resource(
    'dynamodb',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION
)

users_table = dynamodb.Table('Users')
likes_table = dynamodb.Table('Likes')
memes_table = dynamodb.Table('Memes')
likes_table = dynamodb.Table('Likes')
activity_table = dynamodb.Table('ActivityLogs')

def get_presigned_url(key):
    return s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': S3_BUCKET,
            'Key': key
        },
        ExpiresIn=3600   # 1 hour
    )

def log_activity(user_id, action):
    activity_table.put_item(Item={
        'log_id': str(uuid.uuid4()),
        'user_id': user_id,
        'action': action,
        'timestamp': str(datetime.utcnow())
    })




@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Basic validation
        if len(password) < 6:
            return "Password must be 6+ characters"

        # Hash password
        password_hash = pbkdf2_sha256.hash(password)

        # Save to DynamoDB
        users_table.put_item(Item={
            'user_id': str(uuid.uuid4()),
            'username': username,
            'email': email,
            'password': password_hash
        })

        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        # Find user by email
        response = users_table.scan(
            FilterExpression=Attr('email').eq(email)
        )

        if response['Items']:
            user = response['Items'][0]

            # Verify password
            if pbkdf2_sha256.verify(password, user['password']):

                # Store session info
                session['user'] = user['user_id']
                session['username'] = user.get('username', 'User')

                # Log activity
                log_activity(user['user_id'], "LOGIN")

                flash("Login successful!", "success")
                return redirect('/dashboard')

        # If login fails
        flash("Invalid email or password", "danger")
        return redirect('/login')

    return render_template('login.html')

@app.route('/')
def home():
    return redirect('/register')


@app.route('/dashboard')
def dashboard():

    if 'user' not in session:
        return redirect('/login')

    user_id = session['user']

    # Fetch memes uploaded by this user
    response = memes_table.scan(
        FilterExpression=Attr('user_id').eq(user_id)
    )

    memes = response['Items']

    total_memes = len(memes)
    total_likes = sum(m.get('likes', 0) for m in memes)
    total_views = sum(m.get('views', 0) for m in memes)
    total_downloads = sum(m.get('downloads', 0) for m in memes)
    
    recent_memes = memes[:5]

    return render_template(
        'dashboard.html',
        total_memes=total_memes,
        total_likes=total_likes,
        total_views=total_views,
        total_downloads=total_downloads
    )

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION
)

rekognition = boto3.client(
    'rekognition',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION
)

@app.route('/upload', methods=['GET','POST'])
def upload():

    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':

        file = request.files.get('meme')
        title = request.form.get('title')
        category = request.form.get('category')
        description = request.form.get('description')
        tags = request.form.get('tags')
        tags_list = tags.split(",") if tags else []


        # ---------- VALIDATION ----------
        if not title:
            flash("Title is required", "danger")
            return redirect('/upload')

        if not category:
            flash("Category is required", "danger")
            return redirect('/upload')

        if not file:
            flash("Image file is required", "danger")
            return redirect('/upload')

        image_bytes = file.read()

        # ---------- REKOGNITION MODERATION ----------
        response = rekognition.detect_moderation_labels(
            Image={'Bytes': image_bytes}
        )

        for label in response['ModerationLabels']:
            if label['Confidence'] > 60:
                flash(f"Upload blocked: {label['Name']}", "danger")
                return redirect('/upload')

        # ---------- LABEL DETECTION ----------
        labels = rekognition.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=5
        )
        label_list = [l['Name'] for l in labels['Labels']]

        # ---------- TEXT DETECTION ----------
        texts = rekognition.detect_text(Image={'Bytes': image_bytes})
        detected_text = " ".join([t['DetectedText'] for t in texts['TextDetections']])

        meme_id = str(uuid.uuid4())
        key = f"memes/{session['user']}/{meme_id}.jpg"

        response = lambda_client.invoke(
        FunctionName="MemeCategoryLambda",
        InvocationType='RequestResponse',
        Payload=json.dumps({"labels": label_list})
        )   

        suggested_category = json.loads(response['Payload'].read())['category']
        print("AI Suggested Category:", suggested_category)

        # ---------- UPLOAD TO S3 ----------
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=image_bytes,
            ContentType='image/jpeg'
        )

        # ---------- SAVE TO DYNAMODB ----------
        memes_table.put_item(Item={
            'meme_id': meme_id,
            'user_id': session['user'],
            'title': title,
            'description': description,  
            'tags': tags_list,            
            'category': category,
            'likes': 0,
            'views': 0,
            'downloads': 0,
        })



        # ---------- LOG ACTIVITY ----------
        log_activity(session['user'], "UPLOAD_MEME")

        # ---------- SUCCESS POPUP ----------
        flash("Meme uploaded and moderated successfully!", "success")
        return redirect('/upload')

    return render_template('upload.html')

@app.route('/gallery')
def gallery():

    response = memes_table.scan()
    memes = response['Items']

    result = []

    for m in memes:
        key = f"memes/{m['user_id']}/{m['meme_id']}.jpg"
        result.append({
            'meme_id': m['meme_id'],
            'title': m.get('title'),
            'description': m.get('description', ''),
            'tags': m.get('tags', []),
            'likes': m.get('likes',0),
            'views': m.get('views',0),
            'image_url': get_presigned_url(key)
        })

    return render_template('gallery.html', memes=result)

@app.route('/like/<meme_id>')
def like(meme_id):

    if 'user' not in session:
        return redirect('/login')

    # prevent duplicate likes
    existing = likes_table.get_item(
        Key={
            'user_id': session['user'],
            'meme_id': meme_id
        }
    )

    if 'Item' in existing:
        return redirect('/gallery')

    likes_table.put_item(Item={
        'user_id': session['user'],
        'meme_id': meme_id
    })

    memes_table.update_item(
        Key={'meme_id': meme_id},
        UpdateExpression="SET likes = likes + :l",
        ExpressionAttributeValues={":l": 1}
    )
    log_activity(session['user'], f"LIKED_MEME_{meme_id}")


    return redirect('/gallery')

@app.route('/category/<cat>')
def category(cat):

    response = memes_table.scan(
        FilterExpression="category = :c",
        ExpressionAttributeValues={":c": cat}
    )

    memes = response['Items']
    result = []

    for m in memes:
        key = f"memes/{m['user_id']}/{m['meme_id']}.jpg"
        result.append({
            'meme_id': m['meme_id'],
            'title': m['title'],
            'likes': m['likes'],
            'views': m['views'],
            'image_url': get_presigned_url(key)
        })

    return render_template('gallery.html', memes=result)

@app.route('/trending')
def trending():

    response = memes_table.scan()
    memes = response['Items']

    memes.sort(
        key=lambda m: m.get('likes', 0) + (m.get('views', 0) / 10),
        reverse=True
    )


    top = memes[:10]
    result = []

    for m in top:
        key = f"memes/{m['user_id']}/{m['meme_id']}.jpg"
        result.append({
            'meme_id': m['meme_id'],
            'title': m['title'],
            'likes': m['likes'],
            'views': m['views'],
            'image_url': get_presigned_url(key)
        })

    return render_template('gallery.html', memes=result)

@app.route('/like/<meme_id>')
def like_meme(meme_id):

    # User must be logged in
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user']

    # 1️⃣ Check if already liked
    existing = likes_table.get_item(
        Key={
            'user_id': user_id,
            'meme_id': meme_id
        }
    )

    if 'Item' in existing:
        # Already liked → do nothing
        return redirect('/gallery')

    # 2️⃣ Store like record
    likes_table.put_item(Item={
        'user_id': user_id,
        'meme_id': meme_id
    })

    # 3️⃣ Increment likes count safely
    memes_table.update_item(
        Key={'meme_id': meme_id},
        UpdateExpression="SET #l = if_not_exists(#l, :zero) + :inc",
        ExpressionAttributeNames={
            "#l": "likes"
        },
        ExpressionAttributeValues={
            ":inc": 1,
            ":zero": 0
        }
    )

    return redirect('/gallery')

@app.route('/category/<category_name>')
def category_page(category_name):

    response = memes_table.scan(
        FilterExpression=Attr('category').eq(category_name)
    )

    memes = response['Items']
    result = []

    for m in memes:
        key = f"memes/{m['user_id']}/{m['meme_id']}.jpg"

        result.append({
            'meme_id': m['meme_id'],
            'title': m['title'],
            'likes': m.get('likes', 0),
            'views': m.get('views', 0),
            'image_url': get_presigned_url(key)
        })

    return render_template('gallery.html', memes=result)

@app.route('/logout')
def logout():
    if 'user' in session:
        log_activity(session['user'], "LOGOUT")
    session.clear()
    return redirect('/login')

@app.route('/meme/<meme_id>')
def meme_details(meme_id):

    response = memes_table.get_item(Key={'meme_id': meme_id})
    meme = response.get('Item')

    if not meme:
        return "Meme not found"

    key = f"memes/{meme['user_id']}/{meme['meme_id']}.jpg"
    meme['image_url'] = get_presigned_url(key)

    return render_template('meme_details.html', meme=meme)

@app.route('/profile', methods=['GET','POST'])
def profile():

    if 'user' not in session:
        return redirect('/login')

    user_id = session['user']

    if request.method == 'POST':
        email = request.form.get('email')
        bio = request.form.get('bio')

        users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression="SET email=:e, bio=:b",
            ExpressionAttributeValues={
                ":e": email,
                ":b": bio
            }
        )
        flash("Profile updated successfully!", "success")

    user = users_table.get_item(Key={'user_id': user_id})['Item']
    return render_template('profile.html', user=user)

@app.route('/admin')
def admin():

    users = users_table.scan()['Items']
    memes = memes_table.scan()['Items']

    total_users = len(users)
    total_memes = len(memes)

    memes.sort(
        key=lambda m: m.get('likes',0) + m.get('views',0),
        reverse=True
    )

    top_memes = memes[:5]

    return render_template(
        'admin.html',
        total_users=total_users,
        total_memes=total_memes,
        top_memes=top_memes
    )

@app.route('/download/<meme_id>')
def download_meme(meme_id):

    response = memes_table.get_item(Key={'meme_id': meme_id})
    meme = response.get('Item')

    if not meme:
        return "Meme not found"

    # Increment download count
    memes_table.update_item(
        Key={'meme_id': meme_id},
        UpdateExpression="SET downloads = if_not_exists(downloads, :z) + :inc",
        ExpressionAttributeValues={
            ":inc": 1,
            ":z": 0
        }
    )

    # Log activity
    if 'user' in session:
        log_activity(session['user'], f"DOWNLOADED_MEME_{meme_id}")

    # Generate secure download URL
    key = f"memes/{meme['user_id']}/{meme['meme_id']}.jpg"
    url = get_presigned_url(key)

    return redirect(url)
@app.route('/search')
def search():
    query = request.args.get('q')

    response = memes_table.scan(
        FilterExpression=Attr('title').contains(query) |
                         Attr('description').contains(query) |
                         Attr('detected_text').contains(query)
    )

    memes = response['Items']
    result = []

    for m in memes:
        key = f"memes/{m['user_id']}/{m['meme_id']}.jpg"
        m['image_url'] = get_presigned_url(key)
        result.append(m)

    return render_template('gallery.html', memes=result)

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user' not in session:
        return redirect('/login')

    new_pass = request.form.get('password')
    hashed = pbkdf2_sha256.hash(new_pass)

    users_table.update_item(
        Key={'user_id': session['user']},
        UpdateExpression="SET password=:p",
        ExpressionAttributeValues={":p": hashed}
    )

    flash("Password changed successfully!", "success")
    return redirect('/profile')

#print(lambda_client.list_functions()) 

if __name__ == '__main__':
    app.run(debug=True)
