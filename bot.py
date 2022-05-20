"""
This is a chat bot for Twitch with some basic commands, and allows you
to play a game of chess against another chatter.
@Bluepigman5000

"""

import socket
import sys
import ssl
import datetime
import json
from collections import namedtuple
import time
import random
import config
import chess
import chessCommands

Message = namedtuple(
    'Message',
    'prefix user channel irc_command irc_args text text_command text_args',
)


def remove_prefix(string, prefix):
    if not string.startswith(prefix):
        return string
    return string[len(prefix):]


board = chess.Board()
board.reset()


chessGameActive = False
chessGamePending = False
player1 = None
player2 = None
pgn = " "

currentSide = "w"

moveCount = 0

increment = 0

userQuit = False


class Bot:

    def __init__(self):
        # Parameters
        self.irc_server = 'irc.chat.twitch.tv'
        self.irc_port = 6697
        self.oauth_token = config.OAUTH_TOKEN
        self.username = config.username
        self.channels = config.channels
        self.command_prefix = config.prefix
        self.state = {}  # dictionary for cooldown
        self.cooldown = 5  # default cooldown for commands
        self.joke = random.randint(0, 84)
        self.time = time.time()
        self.last_msg = ''
        self.last_msg_time = time.time()

        # anyone can use these
        self.custom_commands = {
            'date': self.reply_with_date,
            'ping': self.reply_to_ping,
            'help': self.list_commands,
            'help_chess': self.reply_with_chesshelp,
            'source_code': self.reply_with_source_code,
            'play_chess': self.play_chess,
            'bot': self.reply_with_bot,
            'ro': self.reply_with_random_opening,
            'joke': self.reply_with_joke,
            'r960': self.reply_with_random960,
            'help_ro': self.reply_with_help_ro,
            'pyramid': self.reply_with_pyramid,
            'slow_pyramid': self.reply_with_slow_pyramid
        }

        # only bot owner can use these commands
        self.private_commands = {
            'leave': self.leave,
            'say': self.say,
            'echo': self.echo,
            'join_channel': self.join_channel,
            'leave_channel': self.part_channel,
            'reset_chess': self.reset_chess
        }

        # commands for playing chess
        self.chess_commands = {
            'join': self.join,
            'white': self.chooseSidePlayer1,
            'black': self.chooseSidePlayer1,
            'move': self.move
        }

    def init(self):
        self.connect()

    def send_privmsg(self, channel, text):
        if text == self.last_msg and (time.time() - self.last_msg_time) < 30:
            text += ' \U000e0000'
            self.send_command(f'PRIVMSG #{channel} : {text}')
            self.last_msg_time = time.time()
            self.last_msg = text
        else:
            self.send_command(f'PRIVMSG #{channel} : {text}')
            self.last_msg_time = time.time()
            self.last_msg = text

    def send_command(self, command):
        if 'PASS' not in command:
            print(f'< {command}')
        self.irc.send((command + '\r\n').encode())

    def connect(self):
        self.irc = ssl.wrap_socket(socket.socket())
        self.irc.connect((self.irc_server, self.irc_port))
        self.send_command(f'PASS {self.oauth_token}')
        self.send_command(f'NICK {self.username}')
        for channel in self.channels:
            self.send_command(f'JOIN #{channel}')
            self.send_privmsg(channel, 'forsenEnter')
        self.loop_for_messages()

    def get_user_from_prefix(self, prefix):
        domain = prefix.split('!')[0]
        if domain.endswith('.tmi.twitch.tv'):
            return domain.replace('.tmi.twitch.tv', '')
        if 'tmi.twitch.tv' not in domain:
            return domain
        return None

    def parse_message(self, received_msg):
        parts = received_msg.split(' ')

        prefix = None
        user = None
        channel = None
        text = None
        text_command = None
        text_args = None
        irc_command = None
        irc_args = None

        if parts[0].startswith(':'):
            prefix = remove_prefix(parts[0], ':')
            user = self.get_user_from_prefix(prefix)
            parts = parts[1:]

        text_start = next(
            (idx for idx, part in enumerate(parts) if part.startswith(':')),
            None
        )
        if text_start is not None:
            text_parts = parts[text_start:]
            text_parts[0] = text_parts[0][1:]
            text = ' '.join(text_parts)
            if text_parts[0].startswith(self.command_prefix):
                text_command = remove_prefix(
                    text_parts[0], self.command_prefix)
                text_args = text_parts[1:]
            parts = parts[:text_start]

        irc_command = parts[0]
        irc_args = parts[1:]

        hash_start = next(
            (idx for idx, part in enumerate(irc_args) if part.startswith('#')),
            None
        )
        if hash_start is not None:
            channel = irc_args[hash_start][1:]

        message = Message(
            prefix=prefix,
            user=user,
            channel=channel,
            text=text,
            text_command=text_command,
            text_args=text_args,
            irc_command=irc_command,
            irc_args=irc_args,
        )

        return message

    def handle_message(self, received_msg):
        if len(received_msg) == 0:
            return

        message = self.parse_message(received_msg)
        # can uncomment these for information on every message
        #print(f'> {message}')
        #print(f'> {received_msg}')

        if message.irc_command == 'PING':
            self.send_command('PONG :tmi.twitch.tv')

        # If message starts with the prefix, follows 1s cooldown
        if message.irc_command == 'PRIVMSG' and \
                message.text.startswith(self.command_prefix) \
                and time.time() - self.time > 1:

            if message.text_command.lower() in self.custom_commands:
                self.custom_commands[message.text_command.lower()](message)
                self.time = time.time()

            if message.text_command.lower() in self.private_commands:
                self.private_commands[message.text_command.lower()](message)
                self.time = time.time()

            if message.text_command.lower() in self.chess_commands:
                self.chess_commands[message.text_command.lower()](message)
                self.time = time.time()

            # Aliases.
            if message.text_command.lower() == "commands":
                self.custom_commands["help"](message)
                self.time = time.time()

    def loop_for_messages(self):
        while True:
            received_msgs = self.irc.recv(4096).decode(errors='ignore')
            for received_msg in received_msgs.split('\r\n'):
                self.handle_message(received_msg)

    """ General Commands here"""

    def reply_with_date(self, message):
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            formatted_date = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
            text = f'{message.user}, the date is {formatted_date} EST.'
            self.send_privmsg(message.channel, text)

    def reply_to_ping(self, message):
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            text = f'@{message.user}, forsenEnter'
            self.send_privmsg(message.channel, text)

    def reply_with_source_code(self, message):
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            text = 'Source code: https://github.com/BluePigman/BluePagmanBot'
            self.send_privmsg(message.channel, text)

    def list_commands(self, message):
        custom_cmd_names = list(self.custom_commands.keys())
        all_cmd_names = [
            self.command_prefix + cmd
            for cmd in custom_cmd_names
        ]
        text = "" f'@{message.user}, Commands: ' + ' '.join(all_cmd_names)
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            self.send_privmsg(message.channel, text)

    def reply_with_bot(self, message):

        text = 'BluePAGMANBot is a bot made by @Bluepigman5000 in Python. \
        It has some basic commands, and can run a game of chess in chat \
        between two different players.'

        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            self.send_privmsg(message.channel, text)

    def reply_with_random_opening(self, message):

        text = f'@{message.user}, '

        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()

            # if args present
            if (message.text_args):

                if '-w' in message.text_args:
                    # get opening for white
                    side = 'w'
                    message.text_args.remove('-w')
                    name = " ".join(message.text_args)
                    if '\U000e0000' in name:
                        name = name.replace('\U000e0000', '')

                    opening = chessCommands.getRandomOpeningSpecific(
                        name, side)
                    self.send_privmsg(message.channel, text + opening)

                elif '-b' in message.text_args:
                    # get opening for black
                    side = 'b'
                    message.text_args.remove('-b')
                    name = " ".join(message.text_args)
                    if '\U000e0000' in name:
                        name = name.replace('\U000e0000', '')

                    opening = chessCommands.getRandomOpeningSpecific(
                        name, side)
                    self.send_privmsg(message.channel, text + opening)

                else:  # get opening for specified search term
                    name = " ".join(message.text_args)
                    if '\U000e0000' in name:
                        name = name.replace('\U000e0000', '')

                    opening = chessCommands.getRandomOpeningSpecific(name)
                    self.send_privmsg(message.channel, text + opening)

            else:  # No arguments
                opening = chessCommands.getRandomOpening()
                self.send_privmsg(message.channel, text + opening)

    def reply_with_random960(self, message):
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            opening = chessCommands.getRandom960()
            self.send_privmsg(message.channel, opening)

    def reply_with_joke(self, message):
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            setup, punchline = chessCommands.getJoke(self.joke)
            self.send_privmsg(message.channel, setup)
            punchline = punchline.strip('\n')
            x = random.randint(0, 10)
            if x > 1:
                response = f'{punchline} haHAA'
            else:
                response = f'{punchline} Pepepains'
            time.sleep(3)
            self.send_privmsg(message.channel, response)
            self.joke += 1
            if self.joke > 84:
                self.joke = 0

    # https://stackoverflow.com/q/6266727
    def reply_with_pyramid(self, message):
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            if len(message.text_args) > 1 and message.text_args[1].isnumeric():
                emote = message.text_args[0]
                width = int(message.text_args[1])
                if len(emote) * width + width - 1 < 500:
                    text = ''
                    for x in range(width):  # go up
                        text += (emote + ' ')
                        self.send_privmsg(message.channel, text)
                        time.sleep(0.1)
                    for y in range(width):  # go down
                        text = text.rsplit(emote, 1)[0]
                        self.send_privmsg(message.channel, text)
                        time.sleep(0.1)
                else:
                    text = 'Pyramid is too large to be displayed in chat. Use \
                    a smaller pyramid width.'
                    self.send_privmsg(message.channel, text)

            else:
                text = 'Width must be an integer. Usage: #pyramid {name} {width}'
                self.send_privmsg(message.channel, text)

    def reply_with_slow_pyramid(self, message):
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            if len(message.text_args) > 1 and message.text_args[1].isnumeric():
                emote = message.text_args[0]
                width = int(message.text_args[1])
                if len(emote) * width + width - 1 < 500:
                    text = ''
                    for x in range(width):  # go up
                        text += (emote + ' ')
                        self.send_privmsg(message.channel, text)
                        time.sleep(1.6)
                    for y in range(width):  # go down
                        text = text.rsplit(emote, 1)[0]
                        self.send_privmsg(message.channel, text)
                        time.sleep(1.6)
                else:
                    text = 'Pyramid is too large to be displayed in chat. Use \
                    a smaller pyramid width.'
                    self.send_privmsg(message.channel, text)

            else:
                text = 'Width must be an integer. Usage: #pyramid {name} {width}'
                self.send_privmsg(message.channel, text)

    """ Chess commands """

    def reply_with_chesshelp(self, message):
        text = (f'@{message.user}, to make a move, type the square of the \
            piece you want to move followed by the square you want to go to, \
            same applies for captures. For example, if you want to move the  \
            pawn from e2 to e4, you type #move e2e4. Input must be in \
            lowercase.')
        text2 = 'For promotions, add the letter \
        of the piece you would like to promote to at the end \
        (e.g. #move g7h8q). To resign type #move resign.'

        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            self.send_privmsg(message.channel, text)
            time.sleep(2)
            self.send_privmsg(message.channel, text2)

    def reply_with_help_ro(self, message):
        text = (f"@{message.user}, Gets a random opening. You can add -b or -w \
for a specific side, and/or add a name for search. e.g. #ro King's Indian \
                Defense -w")
        if (message.user not in self.state or time.time() - self.state[message.user] >
                self.cooldown):
            self.state[message.user] = time.time()
            self.send_privmsg(message.channel, text)

    """Private commands"""

    def leave(self, message):
        text = 'forsenLeave'
        if message.user == config.bot_owner:
            self.send_privmsg(message.channel, text)
            sys.exit()
        else:
            if ("leave" not in self.state or time.time() - self.state["leave"] >
                    self.cooldown):
                self.state["leave"] = time.time()
                self.send_privmsg(message.channel, "NOIDONTTHINKSO")

    def say(self, message):
        if message.user == config.bot_owner:
            self.send_privmsg(message.channel, " ".join(message.text_args))

    # Use: #echo CHANNEL text, will send message text in specified channel.
    def echo(self, message):
        if len(message.text_args) > 1:
            channel = " ".join(message.text_args[0:1])
            text = " ".join(message.text_args[1:])
            if message.user == config.bot_owner:
                self.send_privmsg(channel, text)

    # Work in progress.
    def join_channel(self, message):
        if message.user == config.bot_owner:
            newChannel = " ".join(message.text_args[0:1])
            self.send_command(f'JOIN #{newChannel}')
            self.send_privmsg(newChannel, "forsenEnter")
            self.send_privmsg(message.channel, "Success")

    def part_channel(self, message):
        if message.user == config.bot_owner:
            newChannel = " ".join(message.text_args[0:1])
            self.send_privmsg(newChannel, "forsenLeave")
            self.send_command(f'PART #{newChannel}')

            self.send_privmsg(message.channel, "Success")

    def reset_chess(self, message):
        global choseSide
        global chessGamePending
        global player2Joined
        global chessGameActive
        global pgn
        global pgn
        global moveCount
        global increment
        global currentSide
        choseSide = False
        chessGamePending = False
        player2Joined = False
        chessGameActive = False
        currentSide = 'w'
        board.reset()
        pgn = ''
        moveCount = 0
        increment = 0
        self.send_privmsg(message.channel, "Chess game has been ended.")

    """Global Variables"""

    global player2Joined
    global choseSide
    player2Joined = False
    choseSide = False

    """Functions for chess"""

    # First user to start the initial game, return player
    def getPlayer1(self, message):
        global chessGamePending
        if not chessGamePending:
            chessGamePending = True
            text = f'@{message.user} has started a chess game. Type #join to join \
                the game.'
            self.send_privmsg(message.channel, text)
            global player1
            player1 = message.user

    # Command for when someone types #play, reset variables.
    def play_chess(self, message):
        global pgn
        global moveCount
        global increment
        global currentSide
        currentSide = 'w'
        board.reset()
        pgn = ''
        moveCount = 0
        increment = 0
        global chessGameActive
        if not chessGameActive:
            self.getPlayer1(message)

    # Player 2 that joins the game.
    def getPlayer2(self, message, chessGamePending):
        global player2Joined
        if chessGamePending and not player2Joined:
            player2Joined = True
            text = f'@{message.user} has joined the game.'
            self.send_privmsg(message.channel, text)
            global player2
            player2 = message.user
            time.sleep(2)
            text = f"@{player1}, Choose a side: #white (white), #black (black)"
            self.send_privmsg(message.channel, text)

    # Do this when someone types #join
    def join(self, message):
        if chessGamePending:
            self.getPlayer2(message, chessGamePending)

    # Player who started game chooses side first. (#black or #white)

    def chooseSidePlayer1(self, message):
        global choseSide
        global chessGamePending
        global player2Joined
        global chessGameActive

        if chessGamePending and not choseSide and player2Joined:
            if message.user == player1:

                global player1Side
                global player2Side

                if message.text_command.lower() == "white":
                    choseSide = True
                    text = f"@{player1}, you will play as white"
                    self.send_privmsg(message.channel, text)
                    text = f"@{player1}, you are starting, enter start move."
                    time.sleep(2)
                    self.send_privmsg(message.channel, text)

                    player1Side = "w"
                    player2Side = "b"
                    chessGamePending = False
                    chessGameActive = True

                elif message.text_command.lower() == "black":
                    choseSide = True
                    text = f"@{player1}, you will play as black"
                    self.send_privmsg(message.channel, text)
                    text = f"@{player2}, you are starting, enter start move."
                    time.sleep(2)
                    self.send_privmsg(message.channel, text)
                    player1Side = "b"
                    player2Side = "w"
                    chessGamePending = False
                    chessGameActive = True

                else:
                    text = "Invalid input, please enter \
                    either w for white or b for black."
                    self.send_privmsg(message.channel, text)

    # Start the game

    def move(self, message):
        global currentSide
        global pgn
        global chessGameActive
        global choseSide
        global player2Joined
        global result
        global chessGamePending
        if chessGameActive and not chessGamePending and \
           ("move" not in self.state or time.time() - self.state["move"] >
                2):

            self.state["move"] = time.time()

            # White to play
            if currentSide == 'w':

                if currentSide == player1Side and message.user == player1 \
                        and message.text_command == "move" and \
                        message.text_args:
                    # if list empty (blank text after #move) this wont run
                    move = message.text_args[0]

                    if move == "resign":
                        text = f"@{player1} resigned. @{player2} wins."
                        self.send_privmsg(message.channel, text)
                        chessGameActive = False
                        choseSide = False
                        player2Joined = False
                        time.sleep(2)
                        finalPGN = pgn + " 0-1"
                        pgnMessages = split_pgn(finalPGN)
                        for i in range(0, len(pgnMessages)):
                            self.send_privmsg(message.channel, pgnMessages[i])
                            time.sleep(2)

                    elif chessCommands.checkInput(move):

                        try:
                            # Convert to uci
                            move = chess.Move.from_uci(move)
                            if isLegalMove(move):
                                global moveCount
                                global increment

                                if increment % 2 == 0:
                                    moveCount += 1
                                    pgn += str(moveCount) + ". " +  \
                                        get_san(move) + " "
                                else:
                                    pgn += get_san(move) + " "
                                board.push(move)
                                increment += 1
                                pgnMessages = split_pgn(pgn)
                                for i in range(0, len(pgnMessages)):
                                    self.send_privmsg(message.channel,
                                                      pgnMessages[i])
                                    time.sleep(2)

                                time.sleep(2)

                                if gameOver():
                                    result = result()
                                    self.send_privmsg(message.channel,
                                                      result)
                                    time.sleep(2)
                                    pgnMessages = split_pgn(pgn)
                                    for i in range(0, len(pgnMessages)):
                                        self.send_privmsg(message.channel,
                                                          pgnMessages[i])
                                        time.sleep(2)

                                else:
                                    txt = f"@{player2}, it is your turn."
                                    self.send_privmsg(message.channel, txt)
                                    currentSide = 'b'

                            else:
                                text = "Illegal move, try again"
                                self.send_privmsg(message.channel, text)

                        except:
                            text = "Invalid move, try again."
                            self.send_privmsg(message.channel, text)

                    else:
                        text = "Move does not exist, please try again. \
                        For help refer to #help_chess."
                        self.send_privmsg(message.channel, text)

                elif currentSide == player2Side and message.user == \
                        player2 and message.text_command == "move" and \
                        message.text_args:
                    # if list empty (blank text after #move) this wont run:

                    move = message.text_args[0]
                    if move == "resign":
                        userQuit = True
                        text = f"@{player2} resigned. @{player1} wins."
                        self.send_privmsg(message.channel, text)
                        chessGameActive = False
                        choseSide = False
                        player2Joined = False
                        time.sleep(2)
                        finalPGN = pgn + " 0-1"
                        pgnMessages = split_pgn(finalPGN)
                        for i in range(0, len(pgnMessages)):
                            self.send_privmsg(message.channel, pgnMessages[i])
                            time.sleep(2)

                    elif chessCommands.checkInput(move):
                        # Convert to uci
                        try:

                            move = chess.Move.from_uci(move)
                            if isLegalMove(move):

                                if increment % 2 == 0:
                                    moveCount += 1
                                    pgn += str(moveCount) + ". " + \
                                        get_san(move) + " "
                                else:
                                    pgn += get_san(move) + " "
                                board.push(move)
                                increment += 1

                                if gameOver():
                                    result = result()
                                    self.send_privmsg(message.channel, result)
                                    time.sleep(2)
                                    pgnMessages = split_pgn(pgn)
                                    for i in range(0, len(pgnMessages)):
                                        self.send_privmsg(message.channel,
                                                          pgnMessages[i])
                                        time.sleep(2)

                                else:
                                    pgnMessages = split_pgn(pgn)
                                    for i in range(0, len(pgnMessages)):
                                        self.send_privmsg(message.channel,
                                                          pgnMessages[i])
                                        time.sleep(2)

                                    text = f"@{player1}, it is your turn."
                                    self.send_privmsg(message.channel, text)
                                    currentSide = 'b'

                            else:
                                text = "Illegal move, try again"
                                self.send_privmsg(message.channel, text)
                        except:
                            text = "Invalid move, try again"
                            self.send_privmsg(message.channel, text)

                    else:
                        text = "Move does not exist, please try again. \
                        For help refer to #help_chess."
                        self.send_privmsg(message.channel, text)

            elif currentSide == 'b':

                if currentSide == player1Side and message.user == player1 \
                        and message.text_command == "move" and \
                        message.text_args:
                    # if list empty (blank text after #move) this wont run

                    move = message.text_args[0]
                    if move == "resign":
                        userQuit = True
                        player2Joined = False
                        choseSide = False
                        chessGameActive = False
                        text = f"@{player1} resigned. @{player2} wins."
                        self.send_privmsg(message.channel, text)
                        time.sleep(2)
                        finalPGN = pgn + " 1-0"
                        pgnMessages = split_pgn(finalPGN)
                        for i in range(0, len(pgnMessages)):
                            self.send_privmsg(message.channel, pgnMessages[i])
                            time.sleep(2)

                    elif chessCommands.checkInput(move):
                        try:
                            # Convert to uci
                            move = chess.Move.from_uci(move)
                            if isLegalMove(move):

                                if increment % 2 == 0:
                                    moveCount += 1
                                    pgn += str(moveCount) + ". " + \
                                        get_san(move) + " "
                                else:
                                    pgn += get_san(move) + " "
                                board.push(move)
                                increment += 1

                                if gameOver():
                                    result = result()
                                    self.send_privmsg(message.channel, result)
                                    time.sleep(2)
                                    pgnMessages = split_pgn(pgn)
                                    for i in range(0, len(pgnMessages)):
                                        self.send_privmsg(message.channel,
                                                          pgnMessages[i])
                                        time.sleep(2)

                                else:
                                    pgnMessages = split_pgn(pgn)
                                    for i in range(0, len(pgnMessages)):
                                        self.send_privmsg(message.channel,
                                                          pgnMessages[i])
                                        time.sleep(2)

                                    text = f"@{player2}, it is your turn."
                                    self.send_privmsg(message.channel, text)
                                    currentSide = 'w'

                            else:
                                text = "Illegal move, try again"
                                self.send_privmsg(message.channel, text)
                        except:
                            text = "Invalid move, try again"
                            self.send_privmsg(message.channel, text)

                    else:
                        text = "Move does not exist, please try again. \
                        For help refer to #help_chess."
                        self.send_privmsg(message.channel, text)

                elif currentSide == player2Side and message.user == \
                        player2 and message.text_command == "move" and \
                        message.text_args:
                    # if list empty (blank text after #move) this wont run

                    move = message.text_args[0]

                    if move == "resign":
                        userQuit = True
                        player2Joined = False
                        choseSide = False
                        chessGameActive = False
                        text = f"@{player2} resigned. @{player1} wins."
                        self.send_privmsg(message.channel, text)
                        time.sleep(2)
                        finalPGN = pgn + " 1-0"
                        pgnMessages = split_pgn(finalPGN)
                        for i in range(0, len(pgnMessages)):
                            self.send_privmsg(message.channel, pgnMessages[i])
                            time.sleep(2)

                    elif chessCommands.checkInput(move):
                        try:
                            # Convert to uci
                            move = chess.Move.from_uci(move)
                            if isLegalMove(move):

                                if increment % 2 == 0:
                                    moveCount += 1
                                    pgn += str(moveCount) + ". " + \
                                        get_san(move) + " "
                                else:
                                    pgn += get_san(move) + " "
                                board.push(move)
                                increment += 1

                                if gameOver():
                                    result = result()
                                    self.send_privmsg(message.channel, result)
                                    time.sleep(2)
                                    pgnMessages = split_pgn(pgn)
                                    for i in range(0, len(pgnMessages)):
                                        self.send_privmsg(message.channel,
                                                          pgnMessages[i])
                                        time.sleep(2)

                                else:
                                    pgnMessages = split_pgn(pgn)
                                    for i in range(0, len(pgnMessages)):
                                        self.send_privmsg(message.channel,
                                                          pgnMessages[i])
                                        time.sleep(2)
                                    text = f"@{player1}, it is your turn."
                                    self.send_privmsg(message.channel, text)
                                    currentSide = 'w'

                            else:
                                text = "Illegal move, try again"
                                self.send_privmsg(message.channel, text)
                        except:
                            text = "Invalid move, try again"
                            self.send_privmsg(message.channel, text)

                    else:
                        text = "Move does not exist, please try again. \
                        For help refer to #help_chess."
                        self.send_privmsg(message.channel, text)


def getLegalMoves():
    return list(board.legal_moves)


def isLegalMove(move):
    return (move in list(board.legal_moves))


def getRandomMove():
    legal_moves = list(board.legal_moves)
    return random.choice(legal_moves)

# Check if the game is over (by checkmate, stalemate,
# draw by insufficient material, or draw by fivefold repetition)


def gameOver():
    return board.is_checkmate() or board.is_stalemate() or \
        board.is_insufficient_material() or board.is_fivefold_repetition()

# Return the result of the game in a string. (Player1 wins/Player2 wins/
# stalemate/draw by insufficient material


def result():
    global chessGameActive
    global choseSide
    global player2Joined
    global player1Side
    global pgn

    if board.is_checkmate():
        result = str(board.outcome())
        winner = result[55:]

        if winner[:len(winner) - 1] == "True":  # White wins.
            pgn += ' { White wins by checkmate. } 1-0'
            if player1Side == "w":

                # send player1 wins, then print PGN.
                result = (f"Checkmate, {player1} wins! PogChamp")

                chessGameActive = False
                choseSide = False
                player2Joined = False
                return result

            else:
                # send player2 wins, then print PGN.
                result = (f"Checkmate, {player2} wins! PogChamp")

                chessGameActive = False
                choseSide = False
                player2Joined = False
                return result

        else:  # Black wins
            pgn += ' { Black wins by checkmate. } 0-1'
            if player1Side == "b":
                # Send player 1 wins as black
                result = (f"Checkmate, {player1} wins! PogChamp")
                chessGameActive = False
                choseSide = False
                player2Joined = False
                return result

            else:
                # player 2 wins as black.
                result = (f"Checkmate, {player2} wins! PogChamp")
                chessGameActive = False
                choseSide = False
                player2Joined = False
                return result

    elif board.is_stalemate():  # Check for stalemate
        pgn += ' { Draw by stalemate. } 1/2-1/2'
        result = "Stalemate LUL"
        chessGameActive = False
        choseSide = False
        player2Joined = False
        return result

    elif board.is_insufficient_material():  # Check for draw by insufficient material
        pgn += ' { The game is a draw. } 1/2-1/2'
        result = "Draw by insufficient material."
        chessGameActive = False
        choseSide = False
        player2Joined = False
        return result

    else:  # Fivefold repetition
        pgn += ' { The game is a draw. } 1/2-1/2'
        result = "Draw by fivefold repetition."
        chessGameActive = False
        choseSide = False
        player2Joined = False
        return result


"""
Get standard algebraic notation of move (e2e4 becomes e4).
move is a uci representation of move.
"""


def get_san(move):
    return board.san(move)

# Split the long message into a list of under 500 character messages.
# pgn is a string


def split_pgn(pgn):
    n = 500
    """ Get substrings from i to specified length n, put into list.
    For loop from 0 to length of pgn, increase by n.
    """
    return [pgn[i:i+n] for i in range(0, len(pgn), n)]


def main():
    bot = Bot()
    bot.init()


if __name__ == '__main__':
    main()
