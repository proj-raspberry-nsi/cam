from flask import Flask, render_template, Response, send_file
import cv2, datetime, math, time

app = Flask(__name__)
camera = cv2.VideoCapture(0)

# DÉFINITION (pixels) DES IMAGES
rawImgSize = (int(camera.get(3)), int(camera.get(4)))         # brutes
streamImgSize = (int(rawImgSize[0]/2), int(rawImgSize[1]/2))  # pour la diffusion en direct
videoImgSize  = (int(rawImgSize[0]/2), int(rawImgSize[1]/2))  # pour l'enregistrement

paths = {'pics':'saved_frames','vids':'saved_videos'} # chemins de dossiers pour les images et videos générées
frames = [] # buffer contenant toutes les images pour l'enregistrement video (ponctuel et en continu)
recording = False # booléen : True lorqu'un enregistrement ponctuel est en cours

# NOMBRE DE FRAMES MAXIMALES
videoLen = 100     # pour la video en continu
bufferMaxLen = 500 # pour un enregistrement ponctuel

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
    framerate = len(frames)/(tStop-tStart)
    path = f'{paths["vids"]}/vid{tStop}.avi'
    try:
        out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), framerate, size) # creation de la video
        for frame, time in frames:
            out.write(frame) # ajout de chaque frame
        out.release()   # compilation de la video
        print("nb frames",len(frames))
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
            frames.append([frameRecord, int(time.time())])
            if len(frames) > bufferMaxLen or (len(frames) > videoLen and not recording):
                frames.pop(0)

            # encodage de l'image pour le stream
            ret, buff = cv2.imencode('.jpg', frameStream)
            frameStream = buff.tobytes()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frameStream + b'\r\n')

# page principale
@app.route('/')
def menu():
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
        path = f'{paths["pics"]}/img{int(datetime.datetime.now().timestamp())}.jpg' # créatiion du chemin de dossier pour l'enregistrement
        cv2.imwrite(path,frame) # enregistrement de l'image
        return send_file(path, as_attachment=True) # envoi du fichier
    else:
        return None

# lien de capture puis de télechargement d'une video
@app.route('/download_current_vid')
def download_current_vid():
    global recording, frames
    if recording: # si l'enregistrement est en cours
        recording = False # arret de l'enregistrement
        res, path = saveVid(frames, frames[0][1], frames[-1][1]) # compilation de la video
        if not res: # si la compilation s'est déroulée comme prévu
            return send_file(path, as_attachment=True) # envoi du fichier
        else:
            return None
    else:
        recording = True # debut de l'enregistrement
        frames = [] # réinitialisation du buffer
        return None

# lien télechargement de la video en prise en continu
@app.route('/download_past_vid')
def download_past_vid():
    if frames: # si l'enregistrement en continu a débuté
        res, path = saveVid(frames,frames[0][1],frames[-1][1]) # compilation de la video
        if not res: # si la compilation s'est déroulée comme prévu
            return send_file(path, as_attachment=True) # envoi du fichier
        else:
            print(res) # sinon, affichage de l'erreur
            return None

Flask.run(app,debug=True)