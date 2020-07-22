import os
import requests
from flask import Flask, session, render_template, request, url_for, redirect, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
import util

app = Flask(__name__)

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(util.uri())
db = scoped_session(sessionmaker(bind=engine))

# Log in
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get('name') is None:
            return render_template('login.html')
        else:
            return redirect(url_for('index'))

    if request.method == "POST":
        name = request.form.get("name")
        password = request.form.get("password")
        person = db.execute("SELECT * FROM persons where name = :name", {"name": name}).fetchone()

        if person != None and check_password_hash(person.password, password):
            session['name'] = person.name
            session['id'] = person.personid
            return redirect(url_for("index"))
        else:
            return render_template("login.html", person = person, name = name)

@app.route("/index", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html", name=session['name'])
    else:
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        books = db.execute("SELECT * FROM books where title = :title or author = :author or isbn = :isbn", {"title": title, 'author': author, 'isbn': isbn}).fetchall()
        return render_template('index.html', name=session['name'], books = books)


@app.template_filter()
def nombresito(personID):
    person = db.execute("SELECT * FROM persons where personid = :personid", {"personid": personID}).fetchone()
    return person[1]

#
@app.route("/book/<isbnumber>", methods=['GET', "POST"])
def book(isbnumber):
    if request.method == "GET":
        reviews = db.execute("SELECT * FROM reviews where isbnumber	= :isbnumber", {"isbnumber": isbnumber}).fetchall()
        book = db.execute("SELECT * FROM books where isbn = :isbnumber", {'isbnumber': isbnumber}).fetchone()
        response = requests.get("https://www.goodreads.com/book/review_counts.json?isbns=" + str(isbnumber) + "&key=" + util.apiKey())
        average = response.json()
        average = average['books'][0]['average_rating']
        return render_template("book.html", reviews=reviews, book=book, name=session['name'], average=average)
    else:
        quantity = request.form.get('quantity')
        review = request.form.get('review')
        review_exists = db.execute("SELECT * FROM reviews where personid = :personid and isbnumber = :isbnumber", {'personid': session['id'], 'isbnumber': isbnumber}).fetchone()

        if review_exists == None:
            db.execute("INSERT INTO reviews(value, reviewtext, isbnumber, personid) VALUES (:value, :reviewtext, :isbnumber, :personid)", {'value': quantity, 'reviewtext': review, 'isbnumber': isbnumber, 'personid': session['id']})
            db.commit()
        return redirect(url_for('book', isbnumber=isbnumber))



# Registro
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "GET":
        if session['name'] != None:
            return redirect(url_for('index'))
        else:
            return render_template('registro.html')
    else:
        name = request.form.get("name")
        password = request.form.get("password")
        person = db.execute("SELECT * FROM persons where name = :name", {"name": name}).fetchone()

        if person != None:
            return render_template('registro.html', name = name)
        else:
            password = str(generate_password_hash(password))
            db.execute("INSERT INTO persons(name, password) VALUES (:name, :password)", {'name': name, 'password': password})
            db.commit()
            return redirect(url_for('login'))

@app.route("/logout")
def logout():
    session['name'] = None
    session['id'] = None
    return redirect(url_for('login'))

@app.route("/api/<isbnumber>")
def api(isbnumber):
    book = db.execute("SELECT * FROM books where isbn = :isbn", {"isbn": isbnumber}).fetchone()
    if book == None:
        return jsonify({
            'error': "Error: Ese isbn no existe"
        })
    average_score = db.execute("SELECT AVG(value) FROM reviews where isbnumber = :isbnumber", {"isbnumber": isbnumber}).fetchall()
    review_count = db.execute("SELECT COUNT(value) FROM reviews WHERE isbnumber = :isbnumber", {'isbnumber': isbnumber}).fetchall()
    if average_score == None:
        average_score = 0
    if review_count == None:
        review_count = 0
    
    title = book.title
    author = book.author
    year = book.publicationyear

    return jsonify({
        'title': title,
        'author': author,
        'year': year,
        'isbn': isbnumber,
        'average_score': int(average_score[0][0]),
        'review_count': int(review_count[0][0])
    })

if __name__ == "__main__":
    app.run(debug=True)
