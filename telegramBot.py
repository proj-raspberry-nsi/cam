import requests

class MessageBot:
    def __init__(self, token, chatID=None):
        self.token = token
        self.chatID = chatID

    def getUpdates(self):
        resp = requests.get(f'https://api.telegram.org/bot{self.token}/getUpdates')
        return resp.status_code, resp.content

    def sendMessage(self, message, chatID=None):
        if chatID == None:
            chatID = self.chatID
        resp = requests.get(f'https://api.telegram.org/bot{self.token}/sendMessage?chat_id={chatID}&text={message}')
        return resp.status_code, resp.content

    def sendPhoto(self, path, chatID=None):
        if chatID == None:
            chatID = self.chatID
        method = "sendPhoto"
        params = {'chat_id': chatID}
        file = {'photo': (path, open(path,'rb'))}
        resp = requests.post(f'https://api.telegram.org/bot{self.token}/sendPhoto', files=file, data=params)
        return resp.status_code, resp.content

    def sendVideo(self, path, chatID=None):
        if chatID == None:
            chatID = self.defaultchatID
        method = "sendPhoto"
        params = {'chat_id': chatID}
        file = {'video': (path, open(path,'rb'))}
        resp = requests.post(f'https://api.telegram.org/bot{self.token}/sendVideo', files=file, data=params)
        return resp.status_code, resp.content
