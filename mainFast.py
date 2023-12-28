from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from picamera2 import Picamera2
from libcamera import controls
import uvicorn, cv2, datetime, os, json
import telegramBot # import du programme qui gère la conversation via telegram
import dbManager as database # import du programme qui gère la base de données
import numpy as np

security = HTTPBasic()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# DÉFINITION (pixels) DES IMAGES
rawImgSize    = (1280, 720)      # brutes
streamImgSize = (int(rawImgSize[0]), int(rawImgSize[1]))  # pour la diffusion en direct
videoImgSize  = (int(rawImgSize[0]), int(rawImgSize[1]))  # pour l'enregistrement

camera = Picamera2() # initialisation de la picamera
camera.set_controls({"AfMode": controls.AfModeEnum.Continuous})
camera_config = camera.create_still_configuration({"size":rawImgSize})
camera.configure(camera_config)
camera.start()
font = cv2.FONT_HERSHEY_DUPLEX # import de la typo pour l'affichage de l'heure sur les enregistrements

paths = {'pics':'data/saved_frames',
         'vids':'data/saved_videos'} # chemins de dossiers pour les images et videos générées
frames = [] # buffer contenant toutes les images pour l'enregistrement video (ponctuel et en continu)
recording = False # booléen : True lorqu'un enregistrement ponctuel est en cours

# NOMBRE DE FRAMES MAXIMALES
videoLen = 300     # pour la video en continu
bufferMaxLen = 800 # pour un enregistrement ponctuel

with open('loginInfos.json', 'r') as file: # récupération du token
    loginInfos = json.load(file)
recoveryMode = False


# INITIALISATION DU BOT TELEGRAM
with open('telegramToken.bin', 'rb') as file: # récupération du token
    telegramToken = file.read().decode()
telegram = telegramBot.MessageBot(telegramToken) # initialisation
telegram.chatID = -4079156108 # ID de la conversation
# INITIALISATION DU BOT TELEGRAM

def saveToDB(path, timestamp, vid_or_pic, manual_or_auto):
    db = database.database("database.db")
    if db.getCol("fileStorage", "ID_F"):
        id = max(db.getCol("fileStorage", "ID_F")) + 1
    else:
        id = 0
    size = round(os.path.getsize(path)/1e5)
    storage = [id, path, timestamp, size, vid_or_pic]
    metaDat = [id, manual_or_auto, 0, 0]
    db.insert("fileStorage", storage)
    db.insert("fileMetaData", metaDat)
    db.close()

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


def verification(creds: HTTPBasicCredentials = Depends(security)):
    global recoveryMode, loginInfos
    username = creds.username
    password = creds.password
    if recoveryMode:
        loginInfos["main"]["username"] = creds.username
        loginInfos["main"]["password"] = creds.password
        with open('loginInfos.json', 'w') as file:
            json.dump(loginInfos, file)
        recoveryMode = False
        return True
    elif username == loginInfos["main"]["username"] and password == loginInfos["main"]["password"]:
        return True
    elif username == loginInfos["recovery"]["username"] and password == loginInfos["recovery"]["password"]:
        recoveryMode = True
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return False

# page principale
@app.get('/', response_class=HTMLResponse)
async def home(request: Request, Verifcation = Depends(verification), showLogin:int = 0):
    if Verifcation:
        if showLogin:
            return RedirectResponse("/")
        global recording
        recording = False # arrète tout enregistrement potentiel si la page est re-chargée
        db = database.database("database.db")
        fileStorage  = db.getAll("fileStorage")
        fileMetaData = db.getAll("fileMetaData")
        fileStorage.reverse()
        fileMetaData.reverse()
        dataHist = []
        for i in range(len(fileStorage)):
            now = datetime.datetime.fromtimestamp(int(fileStorage[i][2]))
            date = now.strftime("%d/%m")
            hour = now.strftime("%H:%M")
            size = str(int(fileStorage[i][3])/10) + " Mo"
            dataHist.append(
                (fileStorage[i][0], date, hour, size, fileStorage[i][4], fileMetaData[i][1], fileMetaData[i][2], fileMetaData[i][3])
            )
        return templates.TemplateResponse("index.html", {"request": request, "dataHist":dataHist, "dataHistJson":json.dumps(dataHist)})
    elif not showLogin:
        return RedirectResponse("/recovery?wrongPass=1")
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

# video en continu (stream) utilisée par la page principale
@app.get('/video_feed')
async def video_feed(Verifcation = Depends(verification)):
    if Verifcation:
        return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# lien de capture et télechargement d'une image
@app.get('/download_current_img')
def download_current_img(Verifcation = Depends(verification)):
    if Verifcation:
        frame = camera.capture_array("main")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if frame.shape[:2] == (rawImgSize[1], rawImgSize[0]): # si la camera est disponible
            timestamp = int(datetime.datetime.now().timestamp())
            path = f'{paths["pics"]}/img{timestamp}.jpg' # créatiion du chemin de dossier pour l'enregistrement
            frame = timestampImg(frame, timestamp, videoImgSize, font) # ajout de l'heure en bas à gauche de l'image
            cv2.imwrite(path,frame) # enregistrement de l'image
            saveToDB(path, timestamp, 0, 1)
            return FileResponse(path) # envoi du fichier
        else:
            return Response(status_code=204)

# lien de capture puis de télechargement d'une video
@app.get('/download_current_vid')
def download_current_vid(Verifcation = Depends(verification)):
    if Verifcation:
        global recording, frames
        if recording: # si l'enregistrement est en cours
            if frames:
                recording = False # arret de l'enregistrement
                timestamp = int(datetime.datetime.now().timestamp())
                vid = frames.copy() # création d'une copie (indépendante) de la liste d'images pour éviter que d'autres frames ne soient ajoutées pendant l'execution de "saveVid"
                res, path = saveVid(vid, vid[0][1], timestamp) # compilation de la video
                if not res: # si la compilation s'est déroulée comme prévu
                    saveToDB(path, timestamp, 1, 1)
                    return FileResponse(path) # envoi du fichier
            else:
                print("empty set")
        else:
            recording = True # debut de l'enregistrement
            resetFrames(10) # réinitialisation du buffer
            return Response(status_code=200)
        return Response(status_code=204)

# lien télechargement de la video en prise en continu
@app.get('/download_past_vid')
def download_past_vid(Verifcation = Depends(verification)):
    if Verifcation:
        if frames: # si l'enregistrement en continu a débuté
            timestamp = int(datetime.datetime.now().timestamp())
            vid = frames.copy()
            res, path = saveVid(vid, vid[0][1], timestamp) # compilation de la video
            if not res: # si la compilation s'est déroulée comme prévu
                saveToDB(path, timestamp, 1, 1)
                return FileResponse(path) # envoi du fichier
            else:
                print(res) # sinon, affichage de l'erreur
        return Response(status_code=204)

@app.get('/download_nthfile/')
def download_nthfile(fileID:int, Verifcation = Depends(verification)):
    if Verifcation:
        db = database.database("database.db")
        fileStorage = db.getAll("fileStorage")
        filePath = fileStorage[fileID][1]
        db.close()
        return FileResponse(filePath)

@app.get('/delete_nthfile/')
def delete_nthfile(fileID:int, Verifcation = Depends(verification)):
    if Verifcation:
        db = database.database("database.db")
        fileStorage = db.getAll("fileStorage")
        currentPath = os.path.realpath(os.path.dirname(__name__))
        filePath = currentPath +"/"+ fileStorage[fileID][1]
        os.remove(filePath)
        db.delete("fileStorage", "ID_F", fileID)
        db.delete("fileMetaData", "ID_F", fileID)
        for i in range(fileID, len(fileStorage)+1):
            db.update("fileStorage", "ID_F", str(i), "ID_F", str(i-1))
            db.update("fileMetaData", "ID_F", str(i), "ID_F", str(i-1))
        db.close()
        return Response(status_code=200)

@app.get('/recovery', response_class=HTMLResponse)
def recovery(request: Request, wrongPass:int = False):
    return templates.TemplateResponse("recovery.html", {"request": request, "wrongPass": wrongPass})

#@app.get('/logout', response_class=HTMLResponse)
#def logout(request: Request):
#    return RedirectResponse("/")

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)