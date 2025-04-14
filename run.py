from appFiles import app, ui

if __name__ == '__main__':
    # ui.run() # For Desktop
    app.run(port=8080, debug=True) # For web app
