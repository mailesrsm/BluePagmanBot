import time


def reply_with_chesshelp(bot, message):

        text = (f"""@{message.user}, moves should be entered in either SAN or UCI notation. SAN moves \
            follow the format: letter of piece (except for pawn moves), x if there is a capture, \
            and the coordinate of the square the piece moves to. \
            For pawn promotions add = followed by the letter of the piece. \
            Examples: f6, Nxg5, <Ke2, a1=Q, bxc8=R, Bh8.""")

        text2 = "Sometimes you need to indicate the exact \
            piece that is moving if there is ambiguity. Examples include Nge2, Rhxe1. To castle, enter O-O or O-O-O. \
            Refer to https://en.wikipedia.org/wiki/Portable_Game_Notation#Movetext for more detailed information. "

        text3 = f"""UCI moves follow the format: original coordinate of piece, new coordinate of piece. \
            For castling, use the king's coordinates. UCI Input must be in lowercase and contain no spaces.\
            For example, if you want to start by moving the e pawn to e4, \
            you type {bot.command_prefix}move e4 OR {bot.command_prefix}move e2e4 \
            To resign type {bot.command_prefix}move resign"""

        if (message.user not in bot.state or time.time() - bot.state[message.user] >
                bot.cooldown):
            bot.state[message.user] = time.time()
            bot.send_privmsg(message.channel, text)
            time.sleep(2)
            bot.send_privmsg(message.channel, text2)
            time.sleep(2)
            bot.send_privmsg(message.channel, text3)