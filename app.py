# This is my IA3 Project... I have added a new feature to the app that allows users to favorite games from the IGDB API search results.
import openpyxl
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import requests
import datetime
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
import os
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning

app = Flask(__name__)
app.secret_key = 's3cr3t'

# Set up your IGDB API credentials
CLIENT_ID = 'dx6yicwwoa96meo9uvdg6hjl22cbz7'
ACCESS_TOKEN = 'gy72atxkpmmv2va7l19m5b3zhu4icy'
HEADERS = {
    'Client-ID': CLIENT_ID,
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}

# Set up your Twitch API credentials (store these securely)
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')

gamesdoc = pd.read_excel('/Users/asgibsonpc2022/PycharmProjects/FinalNorthsideDJ/app_ia2/GameData.xlsx')


def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256')


def get_twitch_access_token():
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()['access_token']



# Disable SSL warnings
warnings.simplefilter('ignore', InsecureRequestWarning)


def search_games(query):
    url = 'https://api.igdb.com/v4/games'
    fields = 'name, platforms.name, involved_companies.company.name, first_release_date, rating, websites.url, id'
    data = f'''
        fields {fields};
        search "{query}";
        limit 10;
    '''
    response = requests.post(url, headers=HEADERS, data=data, verify=False)
    games = response.json()
    games_dict = {}
    for game in games:
        game_title = game.get('name', 'Unknown')
        involved_companies = game.get('involved_companies', [])
        developer = 'Unknown'
        publisher = 'Unknown'
        for company in involved_companies:
            if company.get('developer'):
                developer = company['company']['name']
            if company.get('publisher'):
                publisher = company['company']['name']
        game_details = {
            'platform': game.get('platforms', [{'name': 'Unknown'}])[0].get('name'),
            'developer': developer,
            'publisher': publisher,
            'release_date': game.get('first_release_date', 'Unknown'),
            'rating': game.get('rating', 'Unknown'),
            'website': game.get('websites', [{'url': None}])[0].get('url'),
            'id': game.get('id', 'Unknown')
        }
        games_dict[game_title] = game_details
        print(games_dict)
        return games_dict
    else:
        print(f"Error searching games: {response.status_code}, {response.text}")
        return {}


@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.datetime.fromtimestamp(value).strftime('%Y-%m-%d')


@app.route('/toggle_participation/<int:tournament_id>', methods=['POST'])
def toggle_participation(tournament_id):
    if "user" not in session:
        return redirect(url_for('login'))
    user_id = session["user"]
    with sqlite3.connect('Esportsapp.db') as db:
        cursor = db.cursor()
        cursor.execute(f'SELECT 1 FROM tournament_players_{tournament_id} WHERE user_ID = ?', (user_id,))
        participation = cursor.fetchone()
        if participation:
            cursor.execute(f'DELETE FROM tournament_players_{tournament_id} WHERE user_ID = ?', (user_id,))
        else:
            cursor.execute(f'INSERT INTO tournament_players_{tournament_id} (tournament_ID, user_ID) VALUES (?, ?)', (tournament_id, user_id))
        db.commit()
    return redirect(request.referrer or url_for('index'))


# Add this new route to handle toggling favorite games
 #DONT USE THIS ROUTE ANY MORE AS YOU CAN JUST USE THE RESULTS ROUTE WITH
# THE FORM ACTION AND TOGGLE FAVOURITE FUNCTION
def toggle_favorite():
    if "user" not in session:
        return redirect(url_for('login'))
    user_id = session["user"]
    game_id = request.form['game_id']
    action = request.form['action']
    query = request.form['query']
    print("action:", action, "game_id:", game_id,"query:", query, "user_id:", user_id)
    games = search_games(query)
    game = games.get(query)

    if not game:
        flash('Game not found in API search.', 'danger')
        return redirect(url_for('results', query=query))

    game_name = query
    platform = game['platform']
    developer = game['developer']
    publisher = game['publisher']
    release_date = game['release_date']
    rating = game['rating']
    website = game['website']

    with sqlite3.connect('Esportsapp.db') as db:
        cursor = db.cursor()
        if action == "favorite":
            cursor.execute('''
                INSERT INTO fave_games (user_ID, game_ID, game_name, platform, developer, publisher, release_date, rating, website)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, game_id, game_name, platform, developer, publisher, release_date, rating, website))
        elif action == "unfavorite":
            cursor.execute('DELETE FROM fave_games WHERE user_ID = ? AND game_ID = ?', (user_id, game_id))
        db.commit()

    return redirect(url_for('results', query=query))


@app.route('/')
def index():
    if "user" not in session:
        return redirect(url_for('login'))
    user_id = session['user']
    with sqlite3.connect('Esportsapp.db') as db:
        cursor = db.cursor()
        cursor.execute('SELECT username FROM users WHERE user_ID = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            username = result[0]
        else:
            flash('User not found!', 'danger')
            return redirect(url_for('logout'))
        cursor.execute('SELECT * FROM tournament')
        tournaments = cursor.fetchall()
        tournaments_with_participation = []
        for tournament in tournaments:
            tournament_id = tournament[0]
            cursor.execute(f'''
                SELECT u.firstname 
                FROM tournament_players_{tournament_id} tp
                JOIN users u ON tp.user_ID = u.user_ID
            ''')
            players = [row[0] for row in cursor.fetchall()]
            cursor.execute(f'SELECT 1 FROM tournament_players_{tournament_id} WHERE user_ID = ?', (user_id,))
            participating = cursor.fetchone() is not None
            tournaments_with_participation.append((tournament, players, participating))
    return render_template('index.html', username=username, tournaments_with_participation=tournaments_with_participation)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['firstname']
        user_type = request.form['user_type']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        try:
            with sqlite3.connect('Esportsapp.db') as db:
                cursor = db.cursor()
                cursor.execute('INSERT INTO users (firstname, lastname, user_type, email, username, hashed_password) VALUES (?, ?, ?, ?, ?, ?)',
                               (firstname, lastname, user_type, email, username, hashed_password))
                db.commit()
            flash('Registered successfully!', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists!', 'danger')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('Esportsapp.db') as db:
            cursor = db.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            cursor.close()
            if user and check_password_hash(user[6], password):
                session['user'] = user[0]
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form.get('query')
        games = search_games(query)
        return render_template('results.html', query=query, games=games)
    return render_template('search.html')


@app.route('/results', methods=['GET', 'POST'])
def results():
    if "user" not in session:
        return redirect(url_for('login'))
    user_id = session['user']
    query = request.args.get('query')
    if request.method == 'POST':
        print('post request from results page')
        game_id = request.form['game_id']
        action = request.form['action']
        print("action:", action, "game_id:", game_id, "query:", query, "user_id:", user_id)
        games = search_games(query)
        game = games.get(query)

        if not game:
            flash('Game not found in API search.', 'danger')
            return redirect(url_for('results', query=query))

        game_name = query
        platform = game['platform']
        developer = game['developer']
        publisher = game['publisher']
        release_date = game['release_date']
        rating = game['rating']
        website = game['website']
        print("game details:", game_name, platform, developer, publisher, release_date, rating, website)

        with sqlite3.connect('Esportsapp.db') as db:
            cursor = db.cursor()
            if action == "favorite":
                cursor.execute('''
                    INSERT INTO fave_games (user_ID, game_ID, game_name, platform, developer, publisher, release_date, rating, website)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, game_id, game_name, platform, developer, publisher, release_date, rating, website))
            elif action == "unfavorite":
                cursor.execute('DELETE FROM fave_games WHERE user_ID = ? AND game_ID = ?', (user_id, game_id))
            db.commit()
            print("fav game added")

        return redirect(url_for('results', query=query))
    with sqlite3.connect('Esportsapp.db') as db:
        cursor = db.cursor()
        cursor.execute('SELECT game_ID FROM fave_games WHERE user_ID = ?', (user_id,))
        favorite_games = [row[0] for row in cursor.fetchall()]
    return render_template('results.html', query=query, favorite_games=favorite_games)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if "user" not in session:
        return redirect(url_for('login'))
    user_id = session["user"]
    with sqlite3.connect('Esportsapp.db') as db:
        cursor = db.cursor()
        cursor.execute('SELECT username, email, user_type, firstname, lastname FROM users WHERE user_ID = ?', (user_id,))
        user = cursor.fetchone()
        cursor.execute('SELECT game_name, platform, developer, publisher, release_date, rating, website FROM fave_games WHERE user_ID = ?', (user_id,))
        favorite_games = cursor.fetchall()
    if not user:
        return redirect(url_for('index'))
    username, email, user_type, firstname, lastname = user
    if request.method == 'POST':
        email = request.form['email']
        with sqlite3.connect('Esportsapp.db') as db:
            cursor = db.cursor()
            cursor.execute('UPDATE users SET email = ? WHERE user_ID = ?', (email, user_id))
            db.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', username=username, email=email, user_type=user_type, firstname=firstname, lastname=lastname, favorite_games=favorite_games)


if __name__ == '__main__':
    app.run(debug=True)
