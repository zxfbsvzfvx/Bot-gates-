import telebot
from telebot import types



bot = telebot.TeleBot('8539302957:AAGcIKGBkG5Qjxpe57lxmOyHBswk9mvuXwQ')

@bot.message_handler(commands = ['start'])
def start(massage):
  keyboard = types.ReplyKeyboardMarkup(row_width=2)
  button1 = types.KeyboardButton('temp')
  button2 = types.KeyboardButton('open')
  button3 = types.KeyboardButton('close')
  button4 = types.KeyboardButton('help')
  button5 = types.KeyboardButton('status')
  button6 = types.KeyboardButton('reset')
  keyboard.add(button1, button2, button3)

x = +17
@bot.message_handler(func=lambda message: True)
def handle_message(message):
  if message.text == '/temp':
      bot.reply_to(message, 'Температура = ' + str(x) )
  elif message.text == '/open':
      bot.reply_to(message, 'Открываем')
  elif message.text == '/close':
      bot.reply_to(message, 'Закрываем')
  elif message.text == '/status':
      bot.reply_to(message, '')
  elif message.text == '/help':
      bot.reply_to(message, '')
  elif message.text == '/reset':
      bot.reply_to(message, '')
  else:
      bot.reply_to(message, 'Неизвестное сообщение: ' + message.text)
    
bot.polling()