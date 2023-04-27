from fastapi import HTTPException
from pydantic import BaseModel
from ttt import app
import threading
import hashlib
import json
import time

salt = '--secretsauce'
sha256 = lambda n: hashlib.sha256((n+salt).encode()).hexdigest()

class Storage:
	def __init__(self, path):
		self.path = path
		with open(path, 'r') as f:
			self.data = json.load(f)
		threading.Thread(target=self.autosave, daemon=True).start()
	
	def autosave(self):
		while True:
			time.sleep(30)
			with open(self.path, 'w') as f:
				json.dump(self.data, f)

	def __contains__(self, key):
		return key in self.data

	def __getitem__(self, key):
		return self.data[key]

	def __setitem__(self, key, value):
		self.data[key] = value


storage = Storage('chat.json')

class Message(BaseModel):
	text: str
	delete: bool

class Auth(BaseModel):
	user: str
	passw: str

class Send(BaseModel):
	message: Message
	sender: Auth
	reciever: str

class Taken(BaseModel):
	user: str


@app.post('/chat/send')
def send(req: Send):
	if req.sender.user not in storage or req.reciever not in storage:
		raise HTTPException(code=404, detail="User not in database")

	if storage[req.sender.user]['passw'] != sha256(req.sender.passw):
		raise HTTPException(code=403, detail="Invalid password")

	storage[req.reciever]['incoming'].append({'text': req.message.text, 'delete': req.message.delete, 'from': req.sender.user})

@app.post('/chat/signup')
def signup(req: Auth):
	if req.user in storage:
		raise HTTPException(code=409, detail="Username taken")

	storage[req.user] = {'passw': sha256(req.passw), 'incoming': [], 'friends': []}

@app.post('/chat/taken')
def taken(req: Taken):
	return req.user in storage
