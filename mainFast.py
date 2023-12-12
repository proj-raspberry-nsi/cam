from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from picamera2 import Picamera2
from libcamera import controls
import uvicorn, cv2, datetime
import telegramBot # import du programme qui gère la conversation via telegram
import numpy as np

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

camera = Picamera2() # initialisation de la picamera
camera.start()
camera.set_controls({"AfMode": controls.AfModeEnum.Continuous})
font = cv2.FONT_HERSHEY_DUPLEX # import de la typo pour l'affichage de l'heure sur les enregistrements

# DÉFINITION (pixels) DES IMAGES
rawImgSize = camera.preview_configuration.main.size         # brutes
streamImgSize = (int(rawImgSize[0]/2), int(rawImgSize[1]/2))  # pour la diffusion en direct
videoImgSize  = (int(rawImgSize[0]), int(rawImgSize[1]))  # pour l'enregistrement

paths = {'pics':'data/saved_frames',
         'vids':'data/saved_videos'} # chemins de dossiers pour les images et videos générées
frames = [] # buffer contenant toutes les images pour l'enregistrement video (ponctuel et en continu)
recording = False # booléen : True lorqu'un enregistrement ponctuel est en cours

# NOMBRE DE FRAMES MAXIMALES
videoLen = 300     # pour la video en continu
bufferMaxLen = 800 # pour un enregistrement ponctuel

# INITIALISATION DU BOT TELEGRAM
with open('telegramToken.bin', 'rb') as file: # récupération du token
    telegramToken = file.read().decode()
telegram = telegramBot.MessageBot(telegramToken) # initialisation
telegram.chatID = -4079156108 # ID de la conversation

def timestampImg(img, timestamp:int, screensize:(int,int), font, scale=1, color=(0, 100, 255), thickness=1):
    u"""
    affiche la date et l'heure (timestamp) dans le coin en bas à gauche de l'image (img)
    """
    now = datetime.datetime.fromtimestamp(int(timestamp))
    text = now.strftime("%d/%m/%Y %H:%M:%S")
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
    i=0
    while i < len(frames): # retire les quelques images prises après la fin de la vidéo
        if frames[i][1] > tStop:
            frames.pop(i)
        else:
            i+=1

    duration = tStop-tStart
    framerate = len(frames) / duration # choix du framerate en fonction du nombre d'images
    path = f'{paths["vids"]}/vid{int(tStop)}.avi'
    try:
        out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), framerate, videoImgSize) # creation de la video
        for frame, time in frames:
            frame = timestampImg(frame, int(time), videoImgSize, font) # ajout de l'heure en bas à gauche de chaque frame
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
        frame = camera.capture_array("main")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # on redimensionne les images
        frameRecord = cv2.resize(frame, videoImgSize)
        frameStream = cv2.resize(frame, streamImgSize)

        # ajout de la dernière image au buffer et suppression de la première si le buffer a atteint sa limite (qui dépend du mode d'enregistrement : continu ou ponctuel)
        frames.append([frameRecord, datetime.datetime.now().timestamp()])
        if len(frames) > bufferMaxLen or (len(frames) > videoLen and not recording):
            frames.pop(0)

        # encodage de l'image pour le stream
        ret, buff = cv2.imencode('.jpg', frameStream)
        frameStream = buff.tobytes()
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frameStream + b'\r\n')


# page principale
@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    global recording
    recording = False # arrète tout enregistrement potentiel si la page est re-chargée
    return templates.TemplateResponse("index.html", {"request": request})

# video en continu (stream) utilisée par la page principale
@app.get('/video_feed')
async def video_feed():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# lien de capture et télechargement d'une image
@app.get('/download_current_img')
def download_current_img():
    frame = camera.capture_array("main")
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    print("img :", frame.shape, rawImgSize)
    if frame.shape == rawImgSize: # si la camera est disponible
        timestamp = int(datetime.datetime.now().timestamp())
        path = f'{paths["pics"]}/img{timestamp}.jpg' # créatiion du chemin de dossier pour l'enregistrement
        frame = timestampImg(frame, timestamp, videoImgSize, font) # ajout de l'heure en bas à gauche de l'image
        cv2.imwrite(path,frame) # enregistrement de l'image
        return FileResponse(path) # envoi du fichier
    else:
        return Response(status_code=204)

# lien de capture puis de télechargement d'une video
@app.get('/download_current_vid')
def download_current_vid():
    global recording, frames
    if recording: # si l'enregistrement est en cours
        if frames:
            recording = False # arret de l'enregistrement
            timestamp = int(datetime.datetime.now().timestamp())
            vid = frames.copy() # création d'une copie (indépendante) de la liste d'images pour éviter que d'autres frames ne soient ajoutées pendant l'execution de "saveVid"
            res, path = saveVid(vid, vid[0][1], timestamp) # compilation de la video
            if not res: # si la compilation s'est déroulée comme prévu
                return FileResponse(path) # envoi du fichier
        else:
            print("empty set")
    else:
        recording = True # debut de l'enregistrement
        resetFrames(10) # réinitialisation du buffer
    return Response(status_code=204)

# lien télechargement de la video en prise en continu
@app.get('/download_past_vid')
def download_past_vid():
    if frames: # si l'enregistrement en continu a débuté
        timestamp = int(datetime.datetime.now().timestamp())
        vid = frames.copy()
        res, path = saveVid(vid, vid[0][1], timestamp) # compilation de la video
        if not res: # si la compilation s'est déroulée comme prévu
            return FileResponse(path) # envoi du fichier
        else:
            print(res) # sinon, affichage de l'erreur
    return Response(status_code=204)

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)