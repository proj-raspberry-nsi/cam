from flask import Flask, render_template, Response, send_file
import cv2, datetime, math, time

app = Flask(__name__)
camera = cv2.VideoCapture(0)

paths = {'pics':'saved_frames','vids':'saved_videos'}

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, frame = cv2.imencode('.jpg', frame)
            frame = frame.tobytes()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def hello():
    timeAtStart = datetime.datetime.now()
    return render_template('index.html', streamTime=timeAtStart.timestamp())

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/download_current_img')
def download_current_img():
    success, frame = camera.read()
    if success:
        path = f'{paths["pics"]}/img{int(datetime.datetime.now().timestamp())}.jpg'
        cv2.imwrite(path,frame)
    return send_file(path, as_attachment=True)

Flask.run(app,debug=True)