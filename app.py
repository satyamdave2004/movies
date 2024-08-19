from flask import Flask, request, render_template, Response, send_file
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
import math
import requests
import sys
import linecache

app = Flask(__name__)

# Utility function to print exceptions
def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print(f"EXCEPTION IN ({filename}, LINE {lineno} \"{line.strip()}\"): {exc_obj}")

# Check if URL exists
def url_exists(url):
    try:
        response = requests.get(url)
        return response.status_code == 200
    except requests.RequestException:
        return False

# Route to render the home page
@app.route('/')
def index():
    return render_template('index.html')

# Route to process movie/series information
@app.route('/pr/<name>', defaults={'year': None}, methods=['POST', 'GET'])
@app.route('/pr/<name>/<year>', methods=['POST', 'GET'])
def print_report(name, year=None):
    api_key = "d738823c"
    api_url = f"http://www.omdbapi.com/?t={name}&apikey={api_key}"
    if year:
        api_url += f"&y={year}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        data2 = {}
        ep = 0
        ru = None
        release_date_string = '2000-01-01'

        if data:
            imdb_id = data.get('imdbID', "notes")
            if imdb_id:
                mzurl = f"https://api.tvmaze.com/lookup/shows?imdb={imdb_id}"
                if url_exists(mzurl):
                    response2 = requests.get(mzurl)
                    response2.raise_for_status()
                    data2 = response2.json()
                    runt_str = data2.get('averageRuntime', data.get('Runtime', '0'))
                    ru = int(runt_str) if runt_str else 0
                    response3 = requests.get(f"https://api.tvmaze.com/shows/{data2.get('id')}/episodes")
                    data3 = response3.json()
                    ep = len(data3)
                else:
                    data2 = {"error": "No TVMaze Data Found"}
                release_date_string = data2.get('ended') or data.get('Released', 'N/A')

            Released = datetime.strptime(release_date_string, "%d %b %Y").strftime("%Y-%m-%d") if release_date_string != 'N/A' else "2000-01-01"
            return render_template("index2.html", data=data, data2=data2, Released=Released, ep=ep, ru=ru)
        else:
            return Response("<h1 style='color:red'>No Data Found</h1><a href='/'>click here to enter data manually</a>", mimetype="text/html")
    except Exception as e:
        PrintException()
        return Response(f"<h1 style='color:red'>An error occurred: {e}</h1>", mimetype="text/html")

# Route to generate the bill
@app.route('/generate_bill', methods=['POST'])
def generate_bill():
    name = request.form['name']
    content_type = request.form['content_type']
    episodes = int(request.form['episodes'])
    episode_runtime = int(request.form['episode_runtime'])
    release_date = request.form['release_date']
    imdb_rating = float(request.form['imdb_rating'])

    # Calculate charges
    charges = 100
    if content_type == 'movie':
        if episode_runtime > 120:
            charges += math.ceil((episode_runtime - 120) / 20) * 50
        if imdb_rating > 7.5:
            charges += 50
        if imdb_rating > 9:
            charges += 80
    else:
        charges += episodes * 50 + 20 * (math.ceil(episodes / 5) - 1) * episodes
        if episode_runtime > 30:
            charges += episodes * 50
        if imdb_rating > 7.5:
            charges += episodes * 30
        if imdb_rating > 9:
            charges += episodes * 50

    # Additional charges and taxes
    convenience_charge = 50
    release_date = datetime.strptime(release_date, "%Y-%m-%d")
    days_difference = (datetime.now() - release_date).days
    additional_charge = 200 if days_difference <= 45 else 0
    total_charges = charges + convenience_charge + additional_charge
    smst = 0.3 * total_charges
    total_with_tax = total_charges + smst

    # Log the transaction
    log_file_path = "/tmp/display_record.txt"
    with open(log_file_path, "a") as f:
        f.write(f"\n{name},{content_type},{episodes},{episode_runtime},{release_date.strftime('%d-%m-%Y')},{total_charges},{smst},{total_with_tax}")

    return render_template('display.html', name=name, content_type=content_type, episodes=episodes,
                           episode_runtime=episode_runtime, release_date=release_date.strftime('%d-%m-%Y'),
                           imdb_rating=imdb_rating, total_charges=total_charges, smst=smst,
                           total_with_tax=total_with_tax)

# Route to generate and download PDF
@app.route('/download_pdf2', methods=['POST'])
def download_pdf2():
    try:
        name = request.form['name']
        content_type = request.form['content_type']
        episodes = int(request.form['episodes'])
        episode_runtime = int(request.form['episode_runtime'])
        release_date = request.form['release_date']
        imdb_rating = float(request.form['imdb_rating'])

        # String for additional information
        inf = ""

        # Calculate charges
        charges = 100
        if content_type == 'movie':
            if episode_runtime > 120:
                extra_charge = math.ceil((episode_runtime - 120) / 20) * 50
                charges += extra_charge
                inf += f"+ extra for {episode_runtime - 120} minutes = {extra_charge} "
            if imdb_rating > 7.5:
                charges += 50
                inf += "rating(7.5+) charge = 50 "
            if imdb_rating > 9:
                charges += 80
                inf += "rating(9+) charge = 80 "
        else:
            charges += episodes * 50
            inf += f"series charge 100 + {episodes} * 50 = {episodes * 50} "
            charges += 20 * (math.ceil(episodes / 5) - 1) * episodes
            inf += f"\nextra episode charge 20 * {episodes} = {20 * episodes} \n"
            if episode_runtime > 30:
                charges += episodes * 50
                inf += f"+ extra runtime charge {episodes} * 50 = {episodes * 50} "
            if imdb_rating > 9:
                charges += episodes * 50
                inf += f"+ rating(9+) charge = {episodes * 50} "
            if imdb_rating > 7.5:
                charges += episodes * 30
                inf += f"+ rating(7.5+) charge = {episodes * 30} "

        # Calculate taxes and total charges
        convenience_charge = 50
        release_date = datetime.strptime(release_date, "%d-%m-%d")
        days_difference = (datetime.now() - release_date).days
        additional_charge = 200 if days_difference <= 45 else 0
        total_charges = charges + convenience_charge + additional_charge
        smst = 0.3 * total_charges
        total_with_tax = total_charges + smst

        # Generate PDF
        pdf = BytesIO()
        c = canvas.Canvas(pdf)
        c.setFont("Helvetica-Bold", 24)
        c.drawString(30, 780, "INFORMATION")
        c.drawString(30, 750, name)
        c.setFont("Helvetica", 12)
        c.drawString(30, 720, f"Type: {content_type}")
        c.drawString(30, 700, f"Episodes: {episodes}")
        c.drawString(30, 680, f"Episode Runtime: {episode_runtime} minutes")
        c.drawString(30, 660, f"Release Date: {release_date.strftime('%d-%m-%Y')}")
        c.drawString(30, 640, f"IMDb Rating: {imdb_rating}")
        c.setFont("Helvetica-Bold", 24)
        c.drawString(30, 610, "INVOICE")
        c.setFont("Helvetica", 12)
        c.drawString(30, 580, f"Movie/series & Episodes Charge: {charges}")
        c.drawString(30, 560, inf)
        c.drawString(30, 540, f"Convenience Charge: {convenience_charge}")
        c.drawString(30, 520, f"Additional Charge (if released within 45 days): {additional_charge}")
        c.drawString(30, 500, f"SMST CHARGES: {smst}")
        c.setFont("Helvetica-Bold", 14)
        c.drawString(30, 480, f"Total Charges: {total_charges}")
        c.drawString(30, 460, f"Total (Including Tax): {total_with_tax}")
        c.drawString(10, 10, f"Generated at {datetime.now()}")
        c.save()
        pdf.seek(0)

        # Save the PDF and record the transaction
        save_path = f"/tmp/{name}(inv).pdf"
        with open(save_path, 'wb') as file:
            file.write(pdf.read())

        # Log the transaction
        log_file_path = "/tmp/record.txt"
        with open(log_file_path, "a") as f:
            f.write(f"\n{name},{content_type},{episodes},{episode_runtime},{release_date.strftime('%d-%m-%Y')},{total_charges},{smst},{total_with_tax}")

        # Return PDF to user
        pdf.seek(0)
        return send_file(pdf, as_attachment=True, download_name=f"{name}(inv).pdf")

    except Exception as e:
        PrintException()
        return Response(f"<h1 style='color:red'>An error occurred: {e}</h1>", mimetype="text/html")

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=2600)
