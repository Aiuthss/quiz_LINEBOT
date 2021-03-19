from flask import Flask, request, abort
import os
import re
from bs4 import BeautifulSoup
import requests
import random
import config
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError, LineBotApiError)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, RichMenu,RichMenuSize, RichMenuArea, RichMenuBounds, MessageAction, TemplateSendMessage, ButtonsTemplate, PostbackAction, PostbackEvent, TemplateAction)

app = Flask(__name__)

# get env
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]

line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)
switch = 0
categories = ["history","computer","medicine"]
#flag = {}
quiz = {}

page_dict = {}
for category in categories:
    path = category + ".txt"
    with open(path) as f:
        page_dict[category] = [i.strip() for i in f.readlines()]

def createRichmenu():
    try:
        rich_menu_to_create = RichMenu(
            size = RichMenuSize(width=1200,height=300),
            selected = False,
            name = "richmenu for quiz",
            chat_bar_text = "TAP HERE",
            areas=[
                RichMenuArea(
                    bounds=RichMenuBounds(x=0,y=0,width=300,height=300),
                    action=PostbackAction(label="日本史の人物",data="history")
                ),
                RichMenuArea(
                    bounds=RichMenuBounds(x=300,y=0,width=300,height=300),
                    action=PostbackAction(label="コンピュータ",data="computer")
                ),
                RichMenuArea(
                    bounds=RichMenuBounds(x=600,y=0,width=300,height=300),
                    action=PostbackAction(label="医学",data="medicine")
                )
            ]
        )
        richMenuId = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)

        # upload an image for rich menu
        path = 'richmenu.png'

        with open(path, 'rb') as f:
            line_bot_api.set_rich_menu_image(richMenuId, "image/png", f)

        # set the default rich menu
        line_bot_api.set_default_rich_menu(richMenuId)

        result = True

    except Exception as e:
        result = False
        print(str(e))

    return result
    
def make_quiz_button_template(quiz):
    message_template = TemplateSendMessage(
        alt_text = "非対応",
        template = ButtonsTemplate(
            text = quiz["question"][:160],
            actions = [
                PostbackAction(
                    label = quiz["choice"][i][:re.search("\(|\（", quiz["choices"][i]).start()],
                    data = str(i)
                )
                for i in range(4)
            ]
        )
    )
    return message_template

def make_quiz(category):
    reference = make_reference(category)
    print(reference)
    return make_response(reference)

def make_reference(category):
    reference = {}
    words = page_dict[category]
    counter = 0
    while True:
        if counter == 4:
            break
        else:
            try:
                random_word = random.choice(words)
                n = requests.get("https://ja.wikipedia.org/wiki/"+random_word)
                soup = BeautifulSoup(n.text,"html.parser")
                # delete warnings of wikipedia above summary
                for tag in soup.findAll(["tr"]):
                    tag.decompose()

                title = soup.find("h1").text
                soup.find("p").b.decompose()
                summary = soup.find("p").text
                summary = delete_kakko(summary)[:-1]
                reference[title] = summary
            except:
                pass
            else:
                counter += 1
    return reference

def make_response(reference):
    answer = random.choice(range(4))
    question = list(reference.values())[answer]
    choices = list(reference.keys())
    response = []
    for i in range(4):
        if i==answer:
            response.append("正解！" + "\n" + list(reference.keys())[answer] + "\n" + list(reference.values())[answer])
        else:
            response.append("不正解！" + "\n" + list(reference.keys())[answer] + "\n" + list(reference.values())[answer])
    return {"question":question,"choices":choices,"response":response,"answer":answer}

# delete first kakko
def delete_kakko(text):
    depth = 0
    for i,char in enumerate(text):
        if char in ["(","（"]:
            depth += 1
        elif depth == 0:
            break
        elif char in [")","）"]:
            depth -= 1
    text = text[i:]
    text = text[text.find("は")+1:]
    if text[0]=="、":
        text = text[1:]
    return(text)

rich_menu_list = line_bot_api.get_rich_menu_list()
if rich_menu_list == []:
    result = createRichmenu()

@app.route("/")
def hello_world():
    return "hello world!"

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=str(request.get_data())))

@handler.add(PostbackEvent)
def handle_postback(event):
    print(event.postback.data)
#    if event.source.user_id not in flag.keys():
#        flag[event.source.user_id] = 0
    if event.postback.data in categories:
        try:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text="Now Loading..."))
            quiz[event.source.user_id] = make_quiz(event.postback.data)
            quiz_message = make_quiz_button_template(quiz[event.source.user_id])
            line_bot_api.push_message(event.source.user_id,TextSendMessage(text="正しいものはどれ？"))
            line_bot_api.push_message(event.source.user_id,quiz_message)
        except LineBotApiError as e:
            line_bot_api.push_message(event.source.user_id,TextSendMessage(text="Error!"))
            print(str(e))
    elif event.postback.data in ["0","1","2","3"]:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text=quiz[event.source.user_id]["response"][int(event.postback.data)]))
        quiz[event.source.user_id] = None

if __name__ == "__main__":
#    app.run()
    port = int(os.getenv("PORT"))
    app.run(host="0.0.0.0", port=port)
