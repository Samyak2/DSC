from flask import Flask, request, render_template, send_from_directory, session, url_for, redirect
from werkzeug import secure_filename
from img2text import ocr_core
import os
import sys
from scrapers.google_images_scraper import runSpider
from scrapers.youtube_video_scraper import runYouTubeSpider
from scrapers.tenor_gifs_scraper import runGIFSpider
from classify_and_extract import classify_and_extract
import nltk
from dotenv import load_dotenv
load_dotenv()
import pyrebase
import base64
import pickle
import requests

app = Flask(__name__) #initialize flask object
UPLOAD_FOLDER = 'static/uploads/' #folder where uploaded images are to be stored
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
nltk.data.path.append('./nltk_data/')
app.secret_key = "Secret key don't share pls"

config = {
  "apiKey": os.environ['FIREBASE_API_KEY'],
  "authDomain": "recipe-viewer-1.firebaseapp.com",
  "databaseURL": "https://recipe-viewer-1.firebaseio.com",
  "projectId": "recipe-viewer-1",
  "storageBucket": "recipe-viewer-1.appspot.com",
#   "serviceAccount": "firebase-private-key.json",
  "messagingSenderId": "374628466588"
}
firebase = pyrebase.initialize_app(config)
firedb = firebase.database()
auth = firebase.auth()

@app.route("/", methods=["GET", "POST"])
def index():
    print("user" in session)
    if request.method == "POST" and "signout" in request.form:
        print("Signing out")
        auth.current_user = None
        session.pop("user")
    elif request.method == "GET" and "user" in session:
        return render_template("index.html")
    elif request.method == "POST" and "email" in request.form and "password" in request.form:
        try:
            user = auth.sign_in_with_email_and_password(request.form["email"], request.form["password"])
        except requests.exceptions.HTTPError as e:
            response = e.args[0].response
            error = response.json()['error']['message']
            print("ERROR: ", error, file=sys.stderr)
            return render_template("login.html", msg="Invalid username or password")
        session["user"] = user
        return render_template("index.html")
    return render_template("login.html", msg="Login to continue")

@app.route("/createUser", methods=["GET", "POST"])
def create_user():
    if request.method == "POST" and "email" in request.form and "password" in request.form and "confirm_password" in request.form:
        if request.form["password"] == request.form["confirm_password"]:
            try:
                auth.create_user_with_email_and_password(request.form["email"], request.form["password"])
            except requests.exceptions.HTTPError as e:
                response = e.args[0].response
                error = response.json()['error']['message']
                print("ERROR: ", error, file=sys.stderr)
                return redirect(url_for("create_user"))
            return redirect(url_for("index"))
    return render_template("create_user.html")

# words = OrderedDict() #ordered dictionary to store words and corresponding image url
# filename="" #to store name of uploaded image file
# text="" #to store text extracted from image
@app.route("/result", methods=["GET", "POST"]) #first argument is url where the page will be (relative to localhost:5000)
def result():
    # global filename
    # global text
    # global words #use global variables
    #if image is uploaded
    # que = Queue()
    if "video_urls" not in session:
        session["video_urls"] = []
    if "gif_urls" not in session:
        session["gif_urls"] = []
    if "classified_op" not in session:
        session["classified_op"] = []
    if "words" in session:
        for pair in session["words"]:
            pair[1] = os.path.join(app.config['UPLOAD_FOLDER'], pair[0] + " 0.jpg")
    else:
        session["words"] = []
    print(session["words"], file=sys.stderr)
    if request.method == "POST" and "ingsteps" in request.form:
        # print("These are wordsssssss: ",session["words"], file=sys.stderr)
        classified_op = classify_and_extract([i for i,j in session["words"]])
        for lis in classified_op:
            if lis[0] == "ingredients":
                runSpider(lis[1]["name"])
                lis.append(os.path.join(app.config['UPLOAD_FOLDER'], lis[1]["name"] + " 0.jpg"))
        session["classified_op"] = classified_op
        # print(session["classified_op"], file=sys.stderr)
        return render_template("results2.html", 
                words=session["words"], 
                extracted_text=session["text"], 
                img_src=session["filename"], 
                sentences=session["classified_op"],
                video_urls = session["video_urls"],
                gif_urls = session["gif_urls"]
                )
    elif request.method == "POST" and "getvideos" in request.form:
        required_steps = request.form.getlist("required_steps")
        required_steps = list(map(int, required_steps))
        print(list(required_steps), file=sys.stderr)
        session["video_urls"] = []
        print(session["classified_op"], file=sys.stderr)
        allverbs = []
        i = 0
        for sent in session["classified_op"]:
            # print(i, sent[0], required_steps)
            if (sent[0] == "steps") and (i in required_steps):
                # print(i)
                # print(sent)
                allverbs.append(sent[2])
            i += 1
        print(allverbs, file=sys.stderr)
        session["video_urls"].extend(runYouTubeSpider(allverbs))
        video_urls = "https://www.youtube.com/embed/" + session["video_urls"][0] + "?playlist=" + ",".join(session["video_urls"][1:])# + "&autoplay=1"
        session["video_urls"] = video_urls
        return render_template("results2.html", 
                words=session["words"], 
                extracted_text=session["text"], 
                img_src=session["filename"], 
                sentences=session["classified_op"],
                video_urls = session["video_urls"],
                gif_urls = session["gif_urls"]
                )
    elif request.method == "POST" and "getgifs" in request.form:
        session["gif_urls"] = []
        print(session["classified_op"], file=sys.stderr)
        allverbs = []
        for sent in session["classified_op"]:
            if sent[0] == "steps":
                allverbs.extend(sent[1])
        print(allverbs, file=sys.stderr)
        session["gif_urls"].extend(runGIFSpider(allverbs))
        return render_template("results2.html", 
                words=session["words"], 
                extracted_text=session["text"], 
                img_src=session["filename"], 
                sentences=session["classified_op"],
                video_urls = session["video_urls"],
                gif_urls = session["gif_urls"]
                )
    elif request.method == "POST" and "refreshimgs" in request.form:
        return render_template("results2.html", 
                words=session["words"], 
                extracted_text=session["text"], 
                img_src=session["filename"], 
                sentences=session["classified_op"],
                video_urls = session["video_urls"],
                gif_urls = session["gif_urls"]
                )
    # elif request.method == "POST" and "getimgs" in request.form:
    #     for pair in session["words"]:
    #         runSpider(pair[0]) #runs google image scraper (from google_images_scraper.py) to get download the image
    #         pair[1] = os.path.join(app.config['UPLOAD_FOLDER'], pair[0] + " 0.jpg") #add image url to the dict
    #     print(session["words"], file=sys.stderr)
    #     return render_template("results2.html", 
    #             words=session["words"], 
    #             extracted_text=session["text"], 
    #             img_src=session["filename"], 
    #             sentences=session["classified_op"],
    #             video_urls = session["video_urls"],
    #             gif_urls = session["gif_urls"]
    #             )
    elif request.method == "POST":
        print("Running pytesseract!!!!!!!!!!!!!!", file=sys.stderr)
        if "file" not in request.files or request.files["file"].filename == "": #if file is not uploaded
            return render_template("results2.html", msg="No file selected") #Display message, {{msg}} in the html is replaced with the message
        # file = request.files["file"] #get uploaded file
        session["recipe_dict"] = {}
        session["text"] = ""
        session["filename"] = []
        for file in request.files.getlist("file"):
            # filename = secure_filename(file.filename) #get file name
            session["filename"].append(secure_filename(file.filename))
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))) #save file to upload folder
            session["text"] += ocr_core(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))) + "\n" #get image text using ocr_core function from img2txt
        # print(session["text"], file=sys.stderr)
        session["text"] = session["text"].replace('\n', '<br>') #replace newline with <br> so that it is rendered properly in the html
        session["words"] = [["".join(l for l in word if l.isalpha() or l==" " or l.isdigit()),""] for word in nltk.tokenize.sent_tokenize(session["text"].replace("<br><br>", ". ").replace("<br>", " ").replace("..",".")) if len(word)>2] #[word.strip(string.punctuation) for word in text.lower().replace("<br>", " ").split()]) #Get list of words from the text
        session["filename"] = [os.path.join(app.config['UPLOAD_FOLDER'],file) for file in session["filename"]]
        # print("These are wordsssssss: ",session["words"], file=sys.stderr)
        # print(session["words"], file=sys.stderr)
        # for i in session["words"]:
        # print(classify_and_extract([*session["words"]]))
        # t = Thread(target=lambda q, arg1, arg2: q.put(classify_and_extract(arg1,arg2)), args=(que,[*session["words"]],session["classified_op"]))
        # t = Thread(target=classify_and_extract, args=([*session["words"]],session["classified_op"]))
        # t.start()
        # t.join()
        if request.form.get("geting"): 
            classified_op = classify_and_extract([i for i,j in session["words"]])
            for lis in classified_op:
                if lis[0] == "ingredients":
                    runSpider(lis[1]["name"])
                    lis.append(os.path.join(app.config['UPLOAD_FOLDER'], lis[1]["name"] + " 0.jpg"))
            session["classified_op"] = classified_op
            print(session["classified_op"])
        if "classified_op" not in session:
            session["classified_op"] = []
        #load results2.html again with the appropriate message, image source, words list
        if request.form.get("getall"):
            for pair in session["words"]:
                runSpider(pair[0]) #runs google image scraper (from google_images_scraper.py) to get download the image
                pair[1] = os.path.join(app.config['UPLOAD_FOLDER'], pair[0] + " 0.jpg") #add image url to the dict
                # print(words[word], file=sys.stderr)
        return render_template("results2.html", 
            msg="File uploaded successfully", 
            extracted_text=session["text"], 
            img_src=session["filename"], 
            words=session["words"], 
            sentences=session["classified_op"],
            video_urls = session["video_urls"],
            gif_urls = session["gif_urls"]
            )#{word:url for (word, url) in zip(words, urls)})
    #if any "Search for image button is clicked"
    # elif request.method == "GET" and "words" in session:
    #     # session["classified_op"] = que.get()
    #     # print(session["classified_op"], file=sys.stderr)
    #     word = request.args.get("word") #get word
    #     if word is not None and [word, ""] in session["words"]: #if word is found
    #         runSpider(word) #runs google image scraper (from google_images_scraper.py) to get download the image
    #         # session["words"].append((word,os.path.join(app.config['UPLOAD_FOLDER'], word + " 0.jpg"))) #add image url to the dict
    #         session["words"][session["words"].index([word, ""])][1] = os.path.join(app.config['UPLOAD_FOLDER'], word + " 0.jpg")
    #         # print(session["words"][word], file=sys.stderr)
    #     #load results2.html again with the appropriate message, image source, words list
    #     print(session["words"], file=sys.stderr)
    #     return render_template("results2.html", words=session["words"], extracted_text=session["text"], img_src=session["filename"], sentences=session["classified_op"])
    #when the page is first loaded
    else:
        return render_template("results2.html")

#to show image
@app.route("/static/uploads/<file>")
def uploaded_file(file):
    return send_from_directory(UPLOAD_FOLDER, file) #send image

#run flask app when script is run directly
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000)) #get port number from heroku, or use 5000 if run locally
    app.run(debug=True, host='0.0.0.0', port=port)