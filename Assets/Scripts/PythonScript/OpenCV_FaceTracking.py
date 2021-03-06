#!/usr/bin/env python3
import cv2
import numpy as np
import dlib
import socket
import math
import os


UDP_IP = "127.0.0.1"
UDP_PORT = 5065
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
cap = cv2.VideoCapture(0)

width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
 
# Camera internals
focal_length = width   # image width
center = (width/2, height/2)
camera_matrix = np.array(
                         [[focal_length, 0, center[0]],
                         [0, focal_length, center[1]],
                         [0, 0, 1]], dtype = "double"
                         )

print("Camera Matrix :\n {0}".format(camera_matrix))  

# convert 68 (x, y)-coordinates to a NumPy array
def landmarks_to_np(shape, dtype="int"):
    # initialize the list of (x, y)-coordinates
    coords = np.zeros((68, 2), dtype=dtype)  
    # loop over the 68 facial landmarks and convert them to a 2-tuple of (x, y)-coordinates
    for i in range(0, 68):
        coords[i] = (shape.part(i).x, shape.part(i).y)
    return coords

def get_facial_parameter(landmarks):
    d00 =np.linalg.norm(landmarks[27]-landmarks[8]) # Length of face (eyebrow to chin)
    d11 =np.linalg.norm(landmarks[0]-landmarks[16]) # width of face
    d_reference = (d00+d11)/2 	 # a reference distance which is insensitive to the rotation
    # Left eye
    d1 =  np.linalg.norm(landmarks[37]-landmarks[41])
    d2 =  np.linalg.norm(landmarks[38]-landmarks[40])
    # Right eye
    d3 =  np.linalg.norm(landmarks[43]-landmarks[47])
    d4 =  np.linalg.norm(landmarks[44]-landmarks[46])
    # Mouth width
    d5 = np.linalg.norm(landmarks[51]-landmarks[57])
    # Mouth length
    d6 = np.linalg.norm(landmarks[60]-landmarks[64])
    # Left eyebrow to eye distance - Normal
    d7=math.sqrt(np.linalg.norm(landmarks[24]-landmarks[44]))
    # Right eyebrow to eye distance - Normal
    d8=math.sqrt(np.linalg.norm(landmarks[19]-landmarks[37]))
    # Left eyebrow to eye distance - Frown
    d9=math.sqrt(np.linalg.norm(landmarks[21]-landmarks[27]))
    # Right eyebrow to eye distance - Frown
    d10=math.sqrt(np.linalg.norm(landmarks[22]-landmarks[27]))

    leftEyeWid = ((d1+d2)/(2*d_reference) - 0.02)*6
    rightEyewid = ((d3+d4)/(2*d_reference) -0.02)*6
    mouthWid = (d5/d_reference - 0.13)*1.27+0.02
    mouthLen = d6/d_reference
    leftEyebrowLift = d7/d_reference
    rightEyebrowLift = d8/d_reference
    leftFrown = d9/d_reference
    rightFrown = d10/d_reference

    return leftEyeWid, rightEyewid, mouthWid, mouthLen, leftEyebrowLift, rightEyebrowLift, leftFrown, rightFrown

# Head Pose Estimation function: get rotation vector and translation vector       
def head_pose_estimate(image, landmarks):
    
    ##2D image points. 
    image_points = np.array([   landmarks[30],     # Nose tip
                                landmarks[8],      # Chin
                                landmarks[36],     # Left eye left corner
                                landmarks[45],     # Right eye right corne
                                landmarks[1],     # Left head corner
                                landmarks[15]      # Right head corner
                            ], dtype="double")

    # 3D model points.
    model_points = np.array([   (0.0, 0.0, 0.0),             # Nose tip
                                (0.0, -330.0, -65.0),        # Chin
                                (-225.0, 170.0, -135.0),     # Left eye left corner
                                (225.0, 170.0, -135.0),      # Right eye right corne
                                (-349.0, 85.0, -300.0),      # Left head corner
                                (349.0, 85.0, -300.0)        # Right head corner
                         
                            ])

    # Input vector of distortion coefficients, Assuming no lens distortion
    dist_coeffs = np.zeros((4,1))  
    imagePoints = np.ascontiguousarray(image_points[:,:2]).reshape((6,1,2))    
    (success, rotation_vector, translation_vector) = cv2.solvePnP(model_points, imagePoints, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_DLS)
    print("Rotation Vector:\n {0}".format(rotation_vector))
    print("Translation Vector:\n {0}".format(translation_vector))
     
    # visualize the rotation by drawing a line from nose to a 3D point (0, 0, 1000.0)
    (nose_end_point2D, jacobian) = cv2.projectPoints(np.array([(0.0, 0.0, 1000.0)]), rotation_vector, translation_vector, camera_matrix, dist_coeffs)
     
    for p in image_points:
        cv2.circle(image, (int(p[0]), int(p[1])), 3, (0,0,255), -1)  
     
    p1 = ( int(image_points[0][0]), int(image_points[0][1]))
    p2 = ( int(nose_end_point2D[0][0][0]), int(nose_end_point2D[0][0][1]))
     
    cv2.line(image, p1, p2, (255,0,0), 2)
    return success, rotation_vector, translation_vector, camera_matrix, dist_coeffs

# Convert rotation_vector to quaternion component (x,y,z,w)
def convert_to_quaternion(rotation_vector):
        # calculate rotation angles
    theta = cv2.norm(rotation_vector, cv2.NORM_L2)
    
    # transformed to quaterniond
    w = math.cos(theta / 2)
    x = math.sin(theta / 2)*rotation_vector[0][0] / theta
    y = math.sin(theta / 2)*rotation_vector[1][0] / theta
    z = math.sin(theta / 2)*rotation_vector[2][0] / theta
    return round(w,4), round(x,4), round(y,4), round(z,4)

# initialize dlib's pre-trained face detector and load the facial landmark predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# parameters for median filter
windowlen = 5
queue3D_points = np.zeros((windowlen,68,2))
# Smooth filter
def median_filter(input):
    for i in range(windowlen-1):
        queue3D_points[i,:,:] = queue3D_points[i+1,:,:]
    queue3D_points[windowlen-1,:,:] = input
    output = queue3D_points.mean(axis = 0)
    return output

class KalmanFilter:
    def __init__(self, m, q, r):
        self.F = np.eye(m)  # state-transition matrix
        self.H = np.eye(m)  # observation matrix
        self.B = np.eye(m)  # control matrix
        self.K = np.zeros((m,m))  # optimal gain matrix
        self.x = np.zeros(m)  # initial state
        self.P = np.eye(m)  # initial state ccovariance matrix
        self.Q = q * np.eye(m)  # covariance matrix of the process noise
        self.R = r * np.eye(m)  # covariance matrix of the observation noise

    def kalman_predict(self, u):
        self.x = np.dot(self.F, self.x) + np.dot(self.B, u)
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q
        return self.x, self.P

    def kalman_update(self, u, z):
        self.x, self.P = self.kalman_predict(u)
        self.K = self.P.dot(self.H.T).dot( np.linalg.inv(self.H.dot(self.P).dot(self.H.T) + self.R) )
        self.x = self.x + self.K.dot(z - self.H.dot(self.x))
        self.P = self.P - self.K.dot(self.H).dot(self.P)

# Initialize kalman object
# noise covariances Q，R for changing sensitivity
kf_X = KalmanFilter(68, 1,10) 
kf_Y = KalmanFilter(68, 1,10) 
u = np.zeros((68)) # control vector 

# initialize an array for landmarks
landmarks = np.zeros((68,2))

while True:
    ret, frame = cap.read()
    # convert frame into grayscale
    gray_image = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) 
    faces = detector(gray_image, 0)
    
    for face in faces:    
        # determine the facial landmarks for the face region
        shape = predictor(gray_image, face)
        # convert the facial landmark (x, y)-coordinates to a NumPy array (68*2)
        landmarks_orig = landmarks_to_np(shape)

        # Apply kalman filter to landmarks FOR POSE ESTIMATION
        kf_X.kalman_update(u, landmarks_orig[:,0])
        kf_Y.kalman_update(u, landmarks_orig[:,1])
        landmarks[:,0] = kf_X.x.astype(np.int32)
        landmarks[:,1] = kf_Y.x.astype(np.int32)

        landmarks = median_filter(landmarks)

        # Show facial parameter
        leftEyeWid, rightEyewid, mouthWid, mouthLen, leftEyebrowLift, rightEyebrowLift, leftFrown, rightFrown =get_facial_parameter(landmarks)
        print('leftEyeWid:{}, rightEyewid:{}, mouthWid:{}, mouthLen:{}'.format(leftEyeWid, rightEyewid, mouthWid, mouthLen))
        
        # Show head pose
        ret, rotation_vector, translation_vector, camera_matrix, dist_coeffs = head_pose_estimate(frame, landmarks)
        # Convert rotation_vector to quaternion component (x,y,z,w)
        w,x,y,z = convert_to_quaternion(rotation_vector)

        #face_data = str(translation_vector[0,0])+':'+str(translation_vector[1,0])+':'+str(translation_vector[2,0])+':'+str(rotation_vector[0,0])+':'+str(rotation_vector[1,0])+':'+str(rotation_vector[2,0])+':'+str(leftEyeWid)+':'+str(rightEyewid)+':'+str(mouthWid)+':'+str(mouthLen)
        face_data = str(translation_vector[0,0])+':'+str(translation_vector[1,0])+':'+str(translation_vector[2,0])+':'+str(w)+':'+str(x)+':'+str(y)+':'+str(z)+':'+str(leftEyeWid)+':'+str(rightEyewid)+':'+str(mouthWid)+':'+str(mouthLen)+':'+str(leftEyebrowLift)+':'+str(rightEyebrowLift)+':'+str(leftFrown)+':'+str(rightFrown)
        sock.sendto(face_data.encode() , (UDP_IP, UDP_PORT))        
        # loop over the (x, y)-coordinates for the facial landmarks and draw them on the image
        for (x, y) in landmarks_orig:
            cv2.circle(frame, (x, y), 2, (255, 0, 0), -1) 
            
    cv2.imshow('Video', frame)

    key = cv2.waitKey(1)
    if key == 27:
        break
 
cap.release()
cv2.destroyAllWindows()
