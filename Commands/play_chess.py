from threading import Timer


def play_chess(self, message):  # start a game of chess

    if not self.chessGameActive:
        self.chessGameActive = True
        self.player1 = message.user
        text = f'@{self.player1} has started a chess game. Type {self.command_prefix}join to join \
            the game.'
        self.send_privmsg(message.channel, text)
        self.chessTimer = Timer(30, self.gameTimeout, (message.channel,))
        self.chessTimer.start()  # start a timer of 30s.