from flask import Flask, render_template, Response, send_file
import cv2, datetime, math, time

app = Flask(__name__)
camera = cv2.VideoCapture(0)
size = (int(camera.get(3)), int(camera.get(4)))
paths = {'pics':'saved_frames','vids':'saved_videos'}
frames = []
bufferMaxLen = 100

def saveVid(frames,tStart,tStop):
    framerate = len(frames)/(tStop-tStart)
    path = f'{paths["vids"]}/vid{tStop}.avi'
    try:
        out = cv2.VideoWriter(path,
                              cv2.VideoWriter_fourcc(*'MJPG'),
                              framerate, size)
        for frame, time in frames:
            out.write(frame)
        out.release()
    except Exception as error:
        return error, None
    else:
        return None, path

def gen_frames():
    global frames
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            frame = cv2.resize(frame, (240, 135))
            frames.append([frame, int(time.time())])
            if len(frames) > bufferMaxLen:
                frames.pop(0)
            ret, buff = cv2.imencode('.jpg', frame)
            frame = buff.tobytes()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def menu():
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

@app.route('/download_past_vid')
def download_past_vid():
    if frames:
        res, path = saveVid(frames,frames[0][1],frames[-1][1])
        if not res:
            return send_file(path, as_attachment=True)
        else:
            print(res)
            return render_template('index.html', streamTime=1234)

Flask.run(app,debug=True)