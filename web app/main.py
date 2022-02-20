from flask import Flask, url_for, render_template, redirect, request
from flask_sqlalchemy import SQLAlchemy
import pickle
import numpy as np
import torch
import train
from train import BertClassifier
import nltk
import ssl

'''
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download()
'''


app = Flask(__name__)
model = torch.load('models/fine_tuned_bert.pth', map_location=torch.device('cpu') )




@app.route('/')
def index():
    params = [{
        'Layer 1': 30,
        'Layer 2': 50,
        'Layer 3': 20,
        'Layer 4': 10,
    }]
    return render_template('index.html', params=params)

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    params = ['Sentence']
    targets = ['Negative', 'Neutral', 'Positive']
    colors = ['danger', 'primary', 'success']
    if request.method == 'POST':
        data = np.array([request.form.getlist(i) for i in params]).flatten()
        print(data)
        tokenizer = train.get_tokenizer()
        accuracy, preds = train.predict(model, data, np.array([0]), tokenizer, 512, torch.device('cpu'))
        prediction = f"The sentiment is {targets[preds.int().item()]}"
        color = colors[preds.int().item()]
        return render_template('predict.html', parameters=params, prediction=prediction, color=color)
    else:
        return render_template('predict.html', parameters=params, f=0)

@app.route('/metrics')
def metrics():
    return render_template('metrics.html')

@app.route('/Source_code')
def source_code():
    return render_template('Source_code.html')

if __name__ == '__main__':
    app.run(debug=True)