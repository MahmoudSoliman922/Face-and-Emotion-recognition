# boto3 for aws services
import boto3
import cv2
import json
import threading
import requests
import os
import awscam

# aws rekognition client declaration
client = boto3.client('rekognition')
# aws s3 bucket client declaration
s3Client = boto3.client('s3')
# bucket instance
s3 = boto3.resource('s3')
# array of items in the bucket
itemsInBucket = []
# class for setting the detected person name -had to be static so I had to make a class-
class people():
	detected = 'm'
# Threading class that has a return function
class ThreadWithReturnValue(threading.Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs={}, Verbose=None):
        threading.Thread.__init__(self, group, target, name, args, kwargs, Verbose)
        self._return = None
    def run(self):
        if self._Thread__target is not None:
            self._return = self._Thread__target(*self._Thread__args,
                                                **self._Thread__kwargs)
    def join(self):
        threading.Thread.join(self)
        return self._return
# function that returns a list of item in the known people bucket
def getBucketList():
	response = s3Client.list_objects(
    	Bucket='face-rec-final'
    )
	for  item in response['Contents']:
		itemsInBucket.append(item['Key'])
# face comparison function , takes passed_small_frame which is the captured frame from the camera and item which is 
# the item name in the known people bucket
def FacesComp(passed_small_frame ,item):
	response = client.compare_faces(
		SourceImage={
        	'S3Object': {
            	'Bucket': 'my-first12-bucket',
            	'Name': passed_small_frame
        	}
    	},
    	TargetImage={
        	'S3Object': {
            	'Bucket': 'face-rec-final',
            	'Name': item
        	}
    	}
	)
# sets the detected static variable to the detected person name
	if response['FaceMatches'] != []:
		per, ext = item.split('.')
		people.detected = per
# lunches a multiple threads to recognize the person in the frame for time consumption
def faceRecognition(passed_small_frame):
	# i = 0
	# while i < len(itemsInBucket):
	for item in itemsInBucket:
		result = ThreadWithReturnValue(target=FacesComp, args= (passed_small_frame,item,))
		result.start()
		# i += 1
		# if i == len(itemsInBucket):
			# break
		# if (i+1) == len(itemsInBucket):
		# 	people.detected = 'Unknown'
# Emotion recognition function takes only passed_small_frame which is the captured frame
def emotionRecognition(passed_small_frame):
	response = client.detect_faces(
		Image={
			'S3Object': {
            	'Bucket': 'my-first12-bucket',
            	'Name': passed_small_frame
        	}
        },
    	Attributes=[
        	'ALL'
    	]
	)
	maxEmotion = 0
	val = {
	'mood':'',
	'reactions':{
		'happy': '0',
		'sad': '0',
		'angry': '0',
		'calm': '0',
		'disgusted': '0',
		'confused': '0',
		'surprised': '0'
	}
	}
	if response['FaceDetails'] != []:
		faceRec = ThreadWithReturnValue(target=faceRecognition, args= (passed_small_frame,))
		faceRec.start()
		if response['FaceDetails'][0]['Emotions']:
			for item in response['FaceDetails'][0]['Emotions']:
				if item['Confidence'] > maxEmotion:
					maxEmotion = item['Confidence']
					val['mood'] = item['Type']
					val['reactions'][item['Type'].lower()] = int(item['Confidence'])
				else:
					val['reactions'][item['Type'].lower()] = int(item['Confidence'])
		else :
			print("No Emotions found!")
	else:
		print("No faces found!")
		people.detected = 'Unknown'
		val['mood'] = 'Unknown'
	return val
# uploading the captured frame to the bucket to be processed later in emotion recognition and face recognition
def uploadImgTos3(image):
	s3.meta.client.upload_file('/home/aws_cam/Desktop'+image, 'my-first12-bucket', image)
	requestSender(image)
	os.remove(image)
# delete the uploaded image to make sure that the bucket isn't full of old frames
def deleteFroms3(img):
	res = s3Client.delete_object(
    		Bucket='my-first12-bucket',
    		Key=img
	)
 # saves the frame localy to be uploaded later
def saveLocaly(index , frame):
	filename = str(index)+".jpg"
	filename_string = str(filename)
	cv2.imwrite(filename=filename_string,img = frame)
	uploadImgTos3(filename_string)
# this function is responsable for sending the request to the server with the appropriate data
def requestSender(image):
	emotionRec = ThreadWithReturnValue(target=emotionRecognition,args = (image,))
	emotionRec.start()
	# faceRec.start()
	facialEmotions = emotionRec.join()
	while True:
		if people.detected != 'm':
			break
	personName = people.detected
	reac = {
		'happy': facialEmotions['reactions']['happy'],
		'sad': facialEmotions['reactions']['sad'],
		'angry': facialEmotions['reactions']['angry'],
		'calm': facialEmotions['reactions']['calm'],
		'disgusted': facialEmotions['reactions']['disgusted'],
		'confused': facialEmotions['reactions']['confused'],
		'surprised': facialEmotions['reactions']['surprised']
	}
	jsonReac = json.dumps(reac)
	# data = {'name':personName ,'mood':facialEmotions['mood'] ,'reactions':jsonReac}
	# print(data)
	r = requests.post("http://dev.getsooty.com:5000/mobile/deeplens", {'name':personName ,'mood':facialEmotions['mood'] ,'reactions':jsonReac})
	people.detected = 'm'
	deleteFroms3(image)

# Main thread
getBucketList()
# cap = cv2.VideoCapture(1)
imgIndex = 0
while True:
	# retval, frame = cap.read()
	ret, frame = awscam.getLastFrame()
	small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
	saveLocaly(imgIndex,small_frame)
	imgIndex += 1

