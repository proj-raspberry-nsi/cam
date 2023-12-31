from flask import Flask, render_template, Response, send_file
import cv2, datetime, math, time

app = Flask(__name__)
camera = cv2.VideoCapture(0)
font = cv2.FONT_HERSHEY_DUPLEX

# DÉFINITION (pixels) DES IMAGES
rawImgSize = (int(camera.get(3)), int(camera.get(4)))         # brutes
streamImgSize = (int(rawImgSize[0]/4), int(rawImgSize[1]/4))  # pour la diffusion en direct
videoImgSize  = (int(rawImgSize[0]), int(rawImgSize[1]))  # pour l'enregistrement

paths = {'pics':'data/saved_frames','vids':'data/saved_videos'} # chemins de dossiers pour les images et videos générées
frames = [] # buffer contenant toutes les images pour l'enregistrement video (ponctuel et en continu)
recording = False # booléen : True lorqu'un enregistrement ponctuel est en cours

# NOMBRE DE FRAMES MAXIMALES
videoLen = 300     # pour la video en continu
bufferMaxLen = 800 # pour un enregistrement ponctuel
def timestampImg(img, timestamp, screensize, font, scale=1, color=(0, 100, 255), thickness=1):
    now = datetime.datetime.fromtimestamp(int(timestamp))
    text = now.strftime("%H:%M:%S %d/%m/%Y")
    pos = (50, screensize[1] - 50)
    img = cv2.putText(img, text, pos, font, scale, color, thickness, cv2.LINE_AA, False)
    return img

def resetFrames(n:int):
    u"""
    éfface les frames antérieures à la n-ième frame
    """
    global frames
    while len(frames) > n:
        frames.pop(0)

def saveVid(frames,tStart:int,tStop:int)->[str,str]:
    u"""
    - compile le buffer (frames) sous forme de video (.avi) en adaptant le framerate (avec tStart et tStop)
    si la compilation s'est déroulée correctement :
        - renvoie le chemin de dossier de la video enregistrée
    sinon :
        - renvoie l'erreur sans arreter le programme
    """
    duration = tStop-tStart
    framerate = len(frames)/duration
    path = f'{paths["vids"]}/vid{int(tStop)}.avi'
    try:
        out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), framerate, videoImgSize) # creation de la video
        for frame, time in frames:
            frame = timestampImg(frame, int(time), videoImgSize, font)
            out.write(frame) # ajout de chaque frame
        out.release()   # compilation de la video
        print(f"nb frames : {len(frames)}, duration : {duration}s")
    except Exception as error:
        resetFrames(videoLen) # le buffer (frames) est reset pour ne pas accumuler des données inutiles
        return error, None
    else:
        resetFrames(videoLen) # le buffer (frames) est reset pour ne pas accumuler des données inutiles
        return None, path

def gen_frames():
    u"""
    fonction génératrice untiliée pour l'affichage en streaming et pour l'enregistrement des nouvelles frames dans le buffer (frames)
    """
    global frames, recording
    while True:
        success, frame = camera.read()
        if not success:
            break
        else: # si la camera est disponible
            # on redimensionne les images
            frameRecord = cv2.resize(frame, videoImgSize)
            frameStream = cv2.resize(frame, streamImgSize)

            # ajout de la dernière image au buffer et suppression de la première si le buffer a atteint sa limite (qui dépend du mode d'enregistrement : continu ou ponctuel)
            frames.append([frameRecord, time.time()])
            if len(frames) > bufferMaxLen or (len(frames) > videoLen and not recording):
                frames.pop(0)

            # encodage de l'image pour le stream
            ret, buff = cv2.imencode('.jpg', frameStream)
            frameStream = buff.tobytes()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frameStream + b'\r\n')

# page principale
@app.route('/')
def menu():
    global recording
    recording = False
    timeAtStart = datetime.datetime.now()
    return render_template('index.html', streamTime=timeAtStart.timestamp())

# video en continu (stream) utilisée par la page principale
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# lien de capture et télechargement d'une image
@app.route('/download_current_img')
def download_current_img():
    success, frame = camera.read()
    if success: # si la camera est disponible
        timestamp = int(datetime.datetime.now().timestamp())
        path = f'{paths["pics"]}/img{timestamp}.jpg' # créatiion du chemin de dossier pour l'enregistrement
        frame = timestampImg(frame, timestamp, videoImgSize, font)
        cv2.imwrite(path,frame) # enregistrement de l'image
        return send_file(path, as_attachment=True) # envoi du fichier
    else:
        return Response(status=204)

# lien de capture puis de télechargement d'une video
@app.route('/download_current_vid')
def download_current_vid():
    global recording, frames
    if recording: # si l'enregistrement est en cours
        if frames:
            recording = False # arret de l'enregistrement
            res, path = saveVid(frames, frames[0][1], frames[-1][1]) # compilation de la video
            if not res: # si la compilation s'est déroulée comme prévu
                return send_file(path, as_attachment=True) # envoi du fichier
        else:
            print(frames)
    else:
        recording = True # debut de l'enregistrement
        frames = [] # réinitialisation du buffer
    return Response(status=204)

# lien télechargement de la video en prise en continu
@app.route('/download_past_vid')
def download_past_vid():
    if frames: # si l'enregistrement en continu a débuté
        res, path = saveVid(frames,frames[0][1],frames[-1][1]) # compilation de la video
        if not res: # si la compilation s'est déroulée comme prévu
            return send_file(path, as_attachment=True) # envoi du fichier
        else:
            print(res) # sinon, affichage de l'erreur
    return Response(status=204)

Flask.run(app,debug=True)