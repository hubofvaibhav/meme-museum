# Meme Museum 🎭

A cloud-based meme management platform built using Flask and AWS services. Meme Museum allows users to upload, categorize, discover, and interact with memes while leveraging AI-powered content moderation and classification.

## Features

* User Registration & Authentication
* Secure Password Hashing
* Meme Upload & Gallery
* AI-Powered Content Moderation using AWS Rekognition
* Automatic Meme Categorization using AWS Lambda
* Meme Search & Filtering
* Like System
* Trending Memes
* Download Tracking
* User Dashboard & Profile Management
* Activity Logging

## Tech Stack

### Frontend

* HTML
* CSS
* Jinja2 Templates

### Backend

* Python
* Flask

### Cloud Services

* AWS S3 (Image Storage)
* AWS DynamoDB (Metadata Storage)
* AWS Rekognition (Content Moderation & Label Detection)
* AWS Lambda (Category Prediction)

## Architecture

1. User uploads a meme.
2. Flask application receives the image.
3. AWS Rekognition checks for inappropriate content.
4. Rekognition extracts labels and text from the image.
5. AWS Lambda predicts the meme category.
6. Image is stored in Amazon S3.
7. Meme metadata is stored in DynamoDB.
8. Users can browse, like, search, and download memes.

## DynamoDB Tables

* Users
* Memes
* Likes
* ActivityLogs

## Installation

### Clone Repository

```bash
git clone https://github.com/hubofvaibhav/meme-museum.git
cd meme-museum
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Environment

Windows:

```bash
venv\Scripts\activate
```

Linux/Mac:

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file:

```env
AWS_ACCESS_KEY=YOUR_ACCESS_KEY
AWS_SECRET_KEY=YOUR_SECRET_KEY
REGION=ap-south-1
S3_BUCKET=YOUR_BUCKET_NAME
SECRET_KEY=YOUR_FLASK_SECRET
```

### Run Application

```bash
python app.py
```

## Future Enhancements

* Meme Recommendation System
* Social Sharing Features
* AI-Based Meme Caption Generation
* User Following System
* Analytics Dashboard
* Mobile Responsive UI

## Project Highlights

* Implemented cloud-native architecture using AWS services.
* Integrated AI-powered image moderation and classification.
* Designed scalable metadata storage using DynamoDB.
* Built secure authentication and activity tracking features.
* Demonstrated serverless integration using AWS Lambda.

## Author

**Vaibhav Saxena**

* B.Tech in Information Technology
* Cloud & Data Engineering Enthusiast
