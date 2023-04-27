from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Path
from typing import Union, Annotated
from pydantic import BaseModel
import random
import time

class Board:
	def __init__(self, sx, sy):
		self.sizex = sx;
		self.sizey = sy;

		self.players = {}



class Timeline:
	def __init__(self):
		self.events = [];

	def append(self, item):
		ta = (int(time.time()),item)
		self.events.append(ta)

	def get_since(self, time):
		events = []
		for event in self.events[::-1]:
			if time > event[0]:
				return events
			events.append(event)
		return events

actions = ['move', 'shoot', 'heal', 'give', 'upgrade']
secrets = {}

board = Board(20, 10)
timeline = Timeline()

app = FastAPI(ssl_keyfile='key.pem', ssl_certfile='cert.pem')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Params(BaseModel):
	x: Union[int, None]
	y: Union[int, None]
	id: Union[str, None]


class Action(BaseModel):
	action: str
	secret: str
	params: Params

class Update(BaseModel):
	key: str
	value: Union[dict, str, list, int]


def is_overlap(x, y):
	for player in board.players.values():
		if x == player["x"] and y == player["y"]:
			return True
	return False

def is_in_range(r, player, t):
	if abs(player['x']-t['x']) > r:
		return False
	if abs(player['y']-t['y']) > r:
		return False
	return True

def make_non_overlap():
	while True:
		x = random.randint(0, board.sizex-1)
		y = random.randint(0, board.sizey-1)
		if not is_overlap(x, y):
			return x, y

@app.get('/')
def home():
	return {"detail": "welcome!"}

@app.get('/ttt/board')
def board():
	return {"sizex": board.sizex, "sizey": board.sizey, "players": list(board.players.keys())}

@app.get('/ttt/join')
def join():
	while True:
		secret = hex(random.randint(0x10000000, 0xffffffff))[2:]
		player_id = secret[:4]
		if player_id not in secrets.values():
			break
	x, y = make_non_overlap()
	new_player = {"x": x, "y": y, "points": 8, "range": 2, "health": 3}
	secrets[secret] = player_id
	board.players[player_id] = new_player
	timeline.append(player_id)
	return {"id":player_id, "player":new_player, "secret": secret}


@app.post('/ttt/action')
def action(action: Action):
	target = action.params.id
	x = action.params.x
	y = action.params.y
	secret = action.secret
	action = action.action

	# checking if secret and action are valid
	if secret not in secrets:
		raise HTTPException(status_code=403, detail="Invalid secret")
	if action not in actions:
		raise HTTPException(status_code=400, detail="Invalid action")

	# checking if the client provided the required params
	if action in ['shoot', 'heal', 'give']:
		if target == None:
			raise HTTPException(status_code=400, detail="ID value not provided")
	if action == 'move':
		if x == None:
			raise HTTPException(status_code=400, detail="X value not provided")
		if y == None:
			raise HTTPException(status_code=400, detail="Y value not provided")
	player = secrets[secret]

	# checking if player is able to preform action (health and points)
	if board.players[player]['health'] < 1:
		raise HTTPException(status_code=403, detail="You are dead")
	if action in actions[:4]:
		if board.players[player]['points'] < 1:
			raise HTTPException(status_code=403, detail="Not enough points")
	elif board.players[player]['points'] < 3:
		raise HTTPException(status_code=403, detail="Not enough points")

	# if shooting, healing, or giving, we need to check if the recipient is in range of the player
	if action in ['shoot', 'heal', 'give']:
		if not is_in_range(board.players[player]['range'], board.players[player], board.players[target]):
			raise HTTPException(status_code=403, detail="Out of range")

	# if were moving, we need to check if the space is within 1 tile and won't hit another player
	if action == 'move':
		opp = {"x":x, "y":y}
		if not is_in_range(1, board.players[player], opp):
			raise HTTPException(status_code=403, detail="Out of range")
		if is_overlap(x, y):
			raise HTTPException(status_code=403, detail="Player overlap")

	# if all goes well, preform the action
	if action == 'heal':
		if board.players[target]['health'] > 8:
			raise HTTPException(status_code=404, detail="Too much health")
		board.players[target]['health'] += 1
		board.players[player]['points'] -= 1
	elif action == 'shoot':
		board.players[target]['health'] -= 1
		board.players[player]['points'] -= 1
		board.players[target]['health'] = max(0, board.players[target]['health'])
		if board.players[target]['health'] == 0:
			board.players[player]['points'] += board.players[target]['points']
			board.players[target]['points'] = 0
	elif action == 'give':
		board.players[target]['points'] += 1
		board.players[player]['points'] -= 1
	elif action == 'upgrade':
		board.players[player]['range'] += 1
		board.players[player]['points'] -= 3
	elif action == 'move':
		board.players[player]['x'] = x
		board.players[player]['y'] = y
		board.players[player]['points'] -= 1

	# generate json response and add the players to the timeline
	timeline.append(player)
	if action in ['shoot', 'heal', 'give']:
		timeline.append(target)
	return {"detail": "success"}

@app.get('/ttt/player/{player_id}')
def getplayer(player_id: Annotated[str, Path(title="Player ID")]):
	if player_id not in board.players:
		raise HTTPException(status_code=404, detail="Player not found")
	return board.players[player_id]

@app.post('/ttt/players')
def getplayers(player_list: list):
	response = {}
	for player_id in player_list:
		if player_id not in board.players:
			continue
		response[player_id] = board.players[player_id]
	return response

@app.get('/ttt/dev_A58F/dist_points')
def distpoints():
	for player in board.players:
		board.players[player]['points'] += 1
		timeline.append(player)
	return {"detail": "success"}

@app.get('/ttt/since/{time}')
def getsince(time: Annotated[float, Path(title='Timestamp')]):
	events = timeline.get_since(time)
	response = set()
	for event in events:
		response.add(event[1])
	return list(response)

@app.get('/ttt/exists/{player_id}')
def getexists(player_id: Annotated[str, Path(title="Player ID")]):
	if player_id not in board.players:
		return {"exists": False}
	return {"exists": True}

@app.get('/ttt/dev_A58F/remove/{player_id}')
def remove(player_id: Annotated[str, Path(title="Player ID")]):
	del board.players[player_id]
	timeline.append('reload')
	return {"detail": "success"}

@app.get('/ttt/dev_A58F/reload_all')
def ttt_dev_reload():
	timeline.append('reload')
	return {"detail": "success"}

@app.post('/ttt/dev_A58F/update')
def ttt_dev_update(body: Update):
	board.players[body.key].update(body.value)
	timeline.append(body.key)