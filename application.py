
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

# Registro
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "GET":
        if session.get('name') is None:
            return render_template('registro.html')
        else:
            return redirect(url_for('index'))
            
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

@app.route("/index", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html", name=session['name'])
    else:
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')

        if title == "" and author == "" and isbn == "":
            return redirect(url_for('index'))
        elif title == "" and author == "":
            books = db.execute("SELECT * FROM books where isbn = :isbn", {'isbn': isbn}).fetchall()
        else:

            books = db.execute("SELECT * FROM books where title = :title and author = :author and isbn = :isbn", {"title": title, 'author': author, 'isbn': isbn}).fetchall()

            if books == []:
                if title == "":
                    books = db.execute("SELECT * FROM books where author LIKE '%"+author+"%'").fetchall()
                    return render_template('index.html', name=session['name'], books = books)
                if author == "":
                    books = db.execute("SELECT * FROM books where title LIKE '%"+title+"%'").fetchall() 
                    return render_template('index.html', name=session['name'], books = books)             
                
                books = db.execute("SELECT * FROM books where title LIKE '%"+title+"%' or author LIKE '%"+author+"%'").fetchall()
        return render_template('index.html', name=session['name'], books = books)

@app.route("/api_info")
def api_info():
    return render_template("api.html")

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
        else:
            return redirect(url_for('book', isbnumber=isbnumber))
        

@app.route("/logout")
def logout():
    session['name'] = None
    session['id'] = None
    return redirect(url_for('login'))

@app.route("/api/num/<isbnumber>")
def api(isbnumber):
    book = db.execute("SELECT * FROM books where isbn = :isbn", {"isbn": isbnumber}).fetchone()
    if book == None:
        return jsonify({
            'error': "Error: Ese isbn no existe"
        })
    average_score = db.execute("SELECT AVG(value) FROM reviews where isbnumber = :isbnumber", {"isbnumber": isbnumber}).fetchall()
    review_count = db.execute("SELECT COUNT(value) FROM reviews WHERE isbnumber = :isbnumber", {'isbnumber': isbnumber}).fetchall()
    
    if average_score[0][0] == None:
        average_score = 0
    else:
        average_score = int(average_score[0][0])

    if review_count == None:
        review_count = 0
    else:
        review_count = int(review_count[0][0])
    
    title = book.title
    author = book.author
    year = book.publicationyear

    return jsonify({
        'title': title,
        'author': author,
        'year': year,
        'isbn': isbnumber,
        'average_score': average_score,
        'review_count': review_count
    })

@app.route("/api/all")
def api_all():
    books = db.execute("SELECT * FROM books").fetchall()
    if books == None:
        return jsonify({'error': 'Ocurrio un error inesperado, intente mas tarde'})
    return jsonify({'all_books': [dict(row) for row in books]})

@app.route("/api/all_isbn")
def api_all_isbn():
    books = db.execute("SELECT isbn FROM books").fetchall()
    if books == None:
        return jsonify({'error': 'Ocurrio un error'})
    return jsonify({'all_isbnumbers': [dict(row) for row in books]})

@app.route("/api/reviews/<isbn>")
def api_reviews(isbn):
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {'isbn': isbn}).fetchall()
    if book == []:
        return jsonify({"Error": "No existe tal libro"})
    else:
        reviews = db.execute("SELECT value, reviewtext, isbnumber FROM reviews where ISBNumber = :isbn", {'isbn': isbn}).fetchall()
        if reviews == []:
            return jsonify({"No reviews": "El libro pedido no tiene reviews"})
        else:
            return jsonify({'Todas las reviews:': [dict(row) for row in reviews]})
if __name__ == "__main__":
    app.run()
