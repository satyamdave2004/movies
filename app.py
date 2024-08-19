from flask import Flask, request, render_template,Response
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
import math,os,requests,linecache,sys

def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print(f"EXCEPTION IN ({filename}, LINE {lineno} \"{line.strip()}\"): {exc_obj}")

def url_exists(url):
    try:
        response = requests.get(url)
        #print(f"{url} exists and got {response}")
        ans=True if  (200 == response.status_code ) else False
        return ans
    except requests.RequestException:
        return False

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pr/<name>', defaults={'year': None} , methods=['POST','GET'])
@app.route('/pr/<name>,<year>', methods=['POST', 'GET'])
def print_report(name, year=None):
    api_key = "d738823c"
    if year:
        api_url = f"http://www.omdbapi.com/?t={name}&y={year}&apikey={api_key}"
    else:
        api_url = f"http://www.omdbapi.com/?t={name}&apikey={api_key}"

    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise exception for bad responses
        data = response.json()
        data2={}
        ep=0
        ru=None
        release_date_string='2000-01-01'
        if data:
            imdb_id = data.get('imdbID', "notes")
            try:
                ru=int(data.get('Runtime', 'N/A')[:-4])
            except ValueError:
                pass
            if(imdb_id):
             
             mzurl = f"https://api.tvmaze.com/lookup/shows?imdb={imdb_id}"
             print(mzurl)
             if(url_exists(mzurl)):
                response2 = requests.get(mzurl)
                response2.raise_for_status()
                data2 = response2.json()
                runt_str=data2.get('averageRuntime', data.get('Runtime', '0'))
                if(not runt_str):
                    runt_str='0'
                print("hello",runt_str)
                ru=int(runt_str)
                response3 = requests.get(f" https://api.tvmaze.com/shows/{data2.get('id')}/episodes")
                data3=response3.json()
                ep= len(data3)
             else:
                 data2={"error":"No TVMaze Data Found"}
             release_date_string = data2.get('ended') or data.get('Released', 'N/A')
            if release_date_string != 'N/A':
                try:
                    date_object = datetime.strptime(release_date_string, "%d %b %Y")
                except ValueError:
                    date_object = datetime.strptime(release_date_string, "%Y-%m-%d")
                Released = date_object.strftime("%Y-%m-%d")
            else:
                Released = "2000-01-01" 

            return render_template("index2.html", data=data, data2=data2, Released=Released,ep=ep,ru=ru)
        else:
            return Response("<h1 style='color:red'>No Data Found</h1> <a href='/'>click here to enter data manually</a>", mimetype="text/plain")
    except Exception as e:
        print((e.__context__))
        return Response(f"<h1 style='color:red'>An error occurred: {(e)} {PrintException()} </h1> ", mimetype="text/plain")
    
@app.route('/generate_bill', methods=['POST'])
def generate_bill():
    name = request.form['name']
    content_type = request.form['content_type']
    episodes = int(request.form['episodes'])
    episode_runtime = int(request.form['episode_runtime'])
    release_date = request.form['release_date']
    imdb_rating = float(request.form['imdb_rating'])

    # Calculate charges based on the input
    if content_type == 'movie':
        charges = 100
        if episode_runtime > 120:
            charges += math.ceil((episode_runtime - 120) / 20) * 50
        if imdb_rating > 7.5:
            charges += 50
        if imdb_rating > 9:
            charges += 80
    else:
        charges = 100 + (episodes * 50)
        charges += 20*(math.ceil(episodes/5)-1)*episodes
        if episode_runtime > 30:
            charges += episodes * 50
        if imdb_rating > 7.5:
            charges += episodes * 30
        if imdb_rating > 9:
            charges += episodes * 50

    # Calculate taxes
    convenience_charge = 50
    

    # Check if the release date is within 30 days
    release_date = datetime.strptime(release_date, "%Y-%m-%d")
    today = datetime.now()
    days_difference = (today - release_date).days

    if days_difference <= 45:
        additional_charge = 200
    else:
        additional_charge = 0
    
    total_charges = charges + convenience_charge + additional_charge
    smst = 0.3 * total_charges
    total_with_tax = total_charges + smst
    
    with open("C:/Users/91799/Downloads/Telegram Desktop/movies and series data/dispay_record.txt","a") as f:
     f.write(f"\n{name},{content_type},{episodes},{episode_runtime},{release_date.strftime('%d-%m-%Y')},{total_charges},{smst},{total_with_tax}")

    return render_template('display.html', name=name, content_type=content_type, episodes=episodes,
                           episode_runtime=episode_runtime, release_date=release_date.strftime('%d-%m-%Y'),
                           imdb_rating=imdb_rating, total_charges=total_charges, smst=smst,
                           total_with_tax=total_with_tax)


@app.route('/download_pdf2', methods=['POST'])
def download_pdf2():
    try:
        name = request.form['name']
        content_type = request.form['content_type']
        episodes = int(request.form['episodes'])
        episode_runtime = int(request.form['episode_runtime'])
        release_date = request.form['release_date']
        imdb_rating = float(request.form['imdb_rating'])

        # String Make
        inf = ""

        # Calculate charges based on the input
        if content_type == 'movie':
            charges = 100
            inf += "movie charge=100 "
            if episode_runtime > 120:
                charges += math.ceil((episode_runtime - 120) / 20) * 50
                inf += f"+ extra for {episode_runtime - 120} minutes ={math.ceil((episode_runtime - 120) / 20) * 50} "
            if imdb_rating > 7.5:
                charges += 50
                inf += f"rating(7.5+)charge=50 "
            if imdb_rating > 9:
                charges += 80
                inf += f"rating(9+)charge=80 "
        else:
            charges = 100 + (episodes * 50)
            inf += f"\series charge 100 + {episodes} * 50={episodes * 50} "
            charges += 20*(math.ceil(episodes/5)-1)*episodes
            inf += f"\nextra episode 20*({math.ceil(episodes/5)-1})*{episodes} = {20*((episodes/5)-1)*episodes} \n"
            if episode_runtime > 30:
                charges += episodes * 50
                inf += f"+extra runtime charge {episodes} * 50={episodes * 50} "
            if imdb_rating > 9:
                charges += episodes * 50
                inf += f"+rating(9+)charge={episodes} * 50={episodes * 50} "
            if imdb_rating > 7.5:
                charges += episodes * 30
                inf += f"+rating(7.5+)charge {episodes} * 30={episodes * 30} "

        # Calculate taxes
        convenience_charge = 50

        # Check if the release date is within 45 days
        release_date = datetime.strptime(release_date, "%d-%m-%Y")
        today = datetime.now()
        days_difference = (today - release_date).days

        if days_difference <= 45:
            additional_charge = 200
        else:
            additional_charge = 0

        total_charges = charges + convenience_charge + additional_charge
        smst = 0.3 * total_charges
        total_with_tax = total_charges + smst
        print(inf)
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
        c.drawString(30, 520, f"Additional Charge (if released within 30 days): {additional_charge}")
        c.drawString(30, 500, f"SMST CHARGES: {smst}")
        c.setFont("Helvetica-Bold", 14)
        c.drawString(30, 480, f"Total Charges: {total_charges}")
        c.drawString(30, 460, f"Total (Including Tax): {total_with_tax}")
        c.drawString(10, 10, f"Generated at {datetime.now()}")
        c.save()
        pdf.seek(0)

        # Return the PDF for download
        response = Response(pdf.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename={name}(inv).pdf'

        # Save the PDF and record the transaction
        save_path = f'C:/Users/91799/Downloads/Telegram Desktop/movies and series data/{name}(inv).pdf'
        with open(save_path, 'wb') as file:
            file.write(pdf.read())

        with open("C:/Users/91799/Downloads/Telegram Desktop/movies and series data/record.txt", "a") as f:
            f.write(
                f"\n{name},{content_type},{episodes},{episode_runtime},{release_date.strftime('%d-%m-%Y')},{total_charges},{smst},{total_with_tax}"
            )

        return "File saved successfully."
    
    
    except Exception as e:
        return str(e)
        
    #return response
if __name__ == '__main__':
    app.run(debug=True,host="0.0.0.0",port=2600)
