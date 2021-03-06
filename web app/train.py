# -*- coding: utf-8 -*-
"""Train_Pred_Script.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1HjfYxSqVAIY05iaHQ-vWmi-Ph5XTmSoi
"""

# Commented out IPython magic to ensure Python compatibility.
import os
import re
from tqdm import tqdm
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import torch
import nltk
from nltk.corpus import stopwords
from transformers import BertTokenizer
from torch.utils.data import TensorDataset, DataLoader, RandomSampler, SequentialSampler
import torch.nn as nn
from transformers import BertModel
from transformers import AdamW, get_linear_schedule_with_warmup
import random
import time
# %matplotlib inline
nltk.download('stopwords')

class BertClassifier(nn.Module):
    """Bert Model for Classification Tasks.
    """
    def __init__(self, freeze_bert=False):
        """
        @param    bert: a BertModel object
        @param    classifier: a torch.nn.Module classifier
        @param    freeze_bert (bool): Set `False` to fine-tune the BERT model
        """
        super(BertClassifier, self).__init__()
        # Specify hidden size of BERT, hidden size of our classifier, and number of labels
        D_in, H, D_out = 768, 50, 3

        # Instantiate BERT model
        self.bert = BertModel.from_pretrained('bert-base-uncased')

        # Instantiate an one-layer feed-forward classifier
        self.classifier = nn.Sequential(
            nn.Linear(D_in, H),
            nn.ReLU(),
            #nn.Dropout(0.5),
            nn.Linear(H, D_out)
        )

        # Freeze the BERT model
        if freeze_bert:
            for param in self.bert.parameters():
                param.requires_grad = False
        
    def forward(self, input_ids, attention_mask):
        """
        Feed input to BERT and the classifier to compute logits.
        @param    input_ids (torch.Tensor): an input tensor with shape (batch_size,
                      max_length)
        @param    attention_mask (torch.Tensor): a tensor that hold attention mask
                      information with shape (batch_size, max_length)
        @return   logits (torch.Tensor): an output tensor with shape (batch_size,
                      num_labels)
        """
        # Feed input to BERT
        outputs = self.bert(input_ids=input_ids,
                            attention_mask=attention_mask)
        
        # Extract the last hidden state of the token `[CLS]` for classification task
        last_hidden_state_cls = outputs[0][:, 0, :]

        # Feed input to classifier to compute logits
        logits = self.classifier(last_hidden_state_cls)

        return logits

def parse_dataset(X, y, val_percentage, seed):

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=val_percentage, random_state=seed)

    y_train = y_train.astype(np.float64)
    y_val = y_val.astype(np.float64)

    return X_train, X_val, y_train, y_val

def choose_device(dev):
    if torch.cuda.is_available() and dev == 'cuda':       
        device = torch.device("cuda")
        print(f'There are {torch.cuda.device_count()} GPU(s) available.')
        print('Device name:', torch.cuda.get_device_name(0))

    else:
        device = torch.device("cpu")
    return device

def text_preprocessing(s):
    """
    - Lowercase the sentence
    - Change "'t" to "not"
    - Remove "@name"
    - Isolate and remove punctuations except "?"
    - Remove other special characters
    - Remove stop words except "not" and "can"
    - Remove trailing whitespace
    """
    s = s.lower()
    # Change 't to 'not'
    s = re.sub(r"\'t", " not", s)
    # Remove @name
    s = re.sub(r'(@.*?)[\s]', ' ', s)
    # Isolate and remove punctuations except '?'
    s = re.sub(r'([\'\"\.\(\)\!\?\\\/\,])', r' \1 ', s)
    s = re.sub(r'[^\w\s\?]', ' ', s)
    # Remove some special characters
    s = re.sub(r'([\;\:\|?????\n])', ' ', s)
    # Remove stopwords except 'not' and 'can'
    s = " ".join([word for word in s.split()
                  if word not in stopwords.words('english')
                  or word in ['not', 'can']])
    # Remove trailing whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def get_tokenizer():
    # Load the BERT tokenizer
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased', do_lower_case=True)
    return tokenizer

def preprocessing_for_bert(data, tokenizer, max_len):
    """Perform required preprocessing steps for pretrained BERT.
    @param    data (np.array): Array of texts to be processed.
    @return   input_ids (torch.Tensor): Tensor of token ids to be fed to a model.
    @return   attention_masks (torch.Tensor): Tensor of indices specifying which
                  tokens should be attended to by the model.
    """
    # Create empty lists to store outputs
    input_ids = []
    attention_masks = []

    # For every sentence...
    for sent in data:
        # `encode_plus` will:
        #    (1) Tokenize the sentence
        #    (2) Add the `[CLS]` and `[SEP]` token to the start and end
        #    (3) Truncate/Pad sentence to max length
        #    (4) Map tokens to their IDs
        #    (5) Create attention mask
        #    (6) Return a dictionary of outputs
        encoded_sent = tokenizer.encode_plus(
            text=text_preprocessing(sent),  # Preprocess sentence
            add_special_tokens=True,        # Add `[CLS]` and `[SEP]`
            max_length=max_len,                  # Max length to truncate/pad
            pad_to_max_length=True,         # Pad sentence to max length
            #return_tensors='pt',           # Return PyTorch tensor
            return_attention_mask=True      # Return attention mask
            )
        
        # Add the outputs to the lists
        input_ids.append(encoded_sent.get('input_ids'))
        attention_masks.append(encoded_sent.get('attention_mask'))

    # Convert lists to tensors
    input_ids = torch.tensor(input_ids)
    attention_masks = torch.tensor(attention_masks)

    return input_ids, attention_masks

def get_encodings(X, tokenizer, max_length=512, add_special_tokens=True):
    # Encode our concatenated data
    encodings = [tokenizer.encode(sent, max_length=max_length, truncation=True, add_special_tokens=add_special_tokens) for sent in X]
    # Find the maximum length
    max_len = max([len(sent) for sent in encodings])
    return encodings, max_len

def get_inputs_and_masks(X, X_train, X_val, tokenizer, max_len):
    # Print sentence 0 and its encoded token ids
    token_ids = list(preprocessing_for_bert([X[0]], tokenizer, max_len)[0].squeeze().numpy())
    print('Original: ', X[0])
    print('Token IDs: ', token_ids)
    # Run function `preprocessing_for_bert` on the train set and the validation set
    print('Tokenizing data...')
    train_inputs, train_masks = preprocessing_for_bert(X_train, tokenizer, max_len)
    val_inputs, val_masks = preprocessing_for_bert(X_val, tokenizer, max_len)
    return train_inputs, train_masks, val_inputs, val_masks

def to_tensor(X):
    X = torch.tensor(X)
    X = X.type(torch.LongTensor)
    return X

def get_data_loader(train_inputs, train_masks, y_train, val_inputs, val_masks, y_val, batch_size=16):
    # Convert other data types to torch.Tensor
    y_train = to_tensor(y_train)
    y_val = to_tensor(y_val)

    # Create the DataLoader for our training set
    train_inputs_tensor = TensorDataset(train_inputs, train_masks, y_train)
    train_sampler = RandomSampler(train_inputs_tensor)
    train_dataloader = DataLoader(train_inputs_tensor, sampler=train_sampler, batch_size=batch_size)

    # Create the DataLoader for our validation set
    val_inputs_tensor = TensorDataset(val_inputs, val_masks, y_val)
    val_sampler = SequentialSampler(val_inputs_tensor)
    val_dataloader = DataLoader(val_inputs_tensor, sampler=val_sampler, batch_size=batch_size)
    return train_dataloader, val_dataloader

def initialize_model(train_dataloader, device='cuda', epochs=4):
    """Initialize the Bert Classifier, the optimizer and the learning rate scheduler.
    """
    # Instantiate Bert Classifier
    bert_classifier = BertClassifier(freeze_bert=False)

    # Tell PyTorch to run the model on GPU
    bert_classifier.to(device)

    # Create the optimizer
    optimizer = AdamW(bert_classifier.parameters(),
                      lr=5e-5,    # Default learning rate
                      eps=1e-8    # Default epsilon value
                      )

    # Total number of training steps
    total_steps = len(train_dataloader) * epochs

    # Set up the learning rate scheduler
    scheduler = get_linear_schedule_with_warmup(optimizer,
                                                num_warmup_steps=0, # Default value
                                                num_training_steps=total_steps)
    return bert_classifier, optimizer, scheduler

def set_seed(seed_value=42):
    """Set seed for reproducibility.
    """
    random.seed(seed_value)
    np.random.seed(seed_value)
    torch.manual_seed(seed_value)
    torch.cuda.manual_seed_all(seed_value)

loss_fn = nn.CrossEntropyLoss()
def train(model, optimizer, scheduler, train_dataloader, val_dataloader=None, epochs=4, evaluation=False, device='cuda'):
    """Train the BertClassifier model.
    """
    # Start training loop
    
    print("Start training...\n")
    for epoch_i in range(epochs):
        # =======================================
        #               Training
        # =======================================
        # Print the header of the result table
        print(f"{'Epoch':^7} | {'Batch':^7} | {'Train Loss':^12} | {'Val Loss':^10} | {'Val Acc':^9} | {'Elapsed':^9}")
        print("-"*70)

        # Measure the elapsed time of each epoch
        t0_epoch, t0_batch = time.time(), time.time()

        # Reset tracking variables at the beginning of each epoch
        total_loss, batch_loss, batch_counts = 0, 0, 0

        # Put the model into the training mode
        model.train()

        # For each batch of training data...
        for step, batch in enumerate(train_dataloader):
            batch_counts +=1
            # Load batch to GPU
            
            b_input_ids, b_attn_mask, b_labels = tuple(t.to(device) for t in batch)

            # Zero out any previously calculated gradients
            model.zero_grad()

            # Perform a forward pass. This will return logits.
            logits = model(b_input_ids, b_attn_mask)

            # Compute loss and accumulate the loss values
            loss = loss_fn(logits, b_labels)
            batch_loss += loss.item()
            total_loss += loss.item()

            # Perform a backward pass to calculate gradients
            loss.backward()

            # Clip the norm of the gradients to 1.0 to prevent "exploding gradients"
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

            # Update parameters and the learning rate
            optimizer.step()
            scheduler.step()

            # Print the loss values and time elapsed for every 20 batches
            if (step % 20 == 0 and step != 0) or (step == len(train_dataloader) - 1):
                # Calculate time elapsed for 20 batches
                time_elapsed = time.time() - t0_batch

                # Print training results
                print(f"{epoch_i + 1:^7} | {step:^7} | {batch_loss / batch_counts:^12.6f} | {'-':^10} | {'-':^9} | {time_elapsed:^9.2f}")

                # Reset batch tracking variables
                batch_loss, batch_counts = 0, 0
                t0_batch = time.time()

        # Calculate the average loss over the entire training data
        avg_train_loss = total_loss / len(train_dataloader)

        print("-"*70)
        # =======================================
        #               Evaluation
        # =======================================
        if evaluation == True:
            # After the completion of each training epoch, measure the model's performance
            # on our validation set.
            val_loss, val_accuracy = evaluate(model, val_dataloader, device=device)

            # Print performance over the entire training data
            time_elapsed = time.time() - t0_epoch
            
            print(f"{epoch_i + 1:^7} | {'-':^7} | {avg_train_loss:^12.6f} | {val_loss:^10.6f} | {val_accuracy:^9.2f} | {time_elapsed:^9.2f}")
            print("-"*70)
        print("\n")
    
    print("Training complete!")

def evaluate(model, val_dataloader, device='cuda'):
    """After the completion of each training epoch, measure the model's performance
    on our validation set.
    """
    # Put the model into the evaluation mode. The dropout layers are disabled during
    # the test time.
    model.eval()

    # Tracking variables
    val_accuracy = []
    val_loss = []

    # For each batch in our validation set...
    for batch in val_dataloader:
        # Load batch to GPU
        b_input_ids, b_attn_mask, b_labels = tuple(t.to(device) for t in batch)

        # Compute logits
        with torch.no_grad():
            logits = model(b_input_ids, b_attn_mask)

        # Compute loss
        loss = loss_fn(logits, b_labels)
        val_loss.append(loss.item())

        # Get the predictions
        preds = torch.argmax(logits, dim=1).flatten()

        # Calculate the accuracy rate
        accuracy = (preds == b_labels).cpu().numpy().mean() * 100
        val_accuracy.append(accuracy)

    # Compute the average accuracy and loss over the validation set.
    val_loss = np.mean(val_loss)
    val_accuracy = np.mean(val_accuracy)

    return val_loss, val_accuracy

def predict(model, X_test, y_test, tokenizer, max_len, device='cuda'):
    test_inputs, test_masks = preprocessing_for_bert(X_test, tokenizer, max_len)
    y_test = y_test.astype(np.float64)
    with torch.no_grad():
        test_inputs, test_masks = test_inputs.to(device), test_masks.to(device)
        logits = model(test_inputs, test_masks)
        preds = torch.argmax(logits, dim=1).flatten().to('cpu')
    accuracy = np.mean(y_test == preds.numpy().astype(np.float64))*100
    return accuracy, preds

def train_and_predict(X, y, X_test, y_test, val_percentage, epochs=4):
    X_train, X_val, y_train, y_val = parse_dataset(X, y, val_percentage, seed)
    device = choose_device('cuda')
    print(f'X Shape: {X.shape}')
    print(f'X_train Shape: {X_train.shape}')
    print(f'X_val Shape: {X_val.shape}')
    print(f'X_test Shape: {X_test.shape}')
    print(f'y Shape: {y.shape}')
    print(f'y_train Shape: {y_train.shape}')
    print(f'y_val Shape: {y_val.shape}')
    print(f'y_test Shape: {y_test.shape}')
    print(f'Device: {device}')
    tokenizer = get_tokenizer()
    encodings, max_len = get_encodings(X, tokenizer)
    print(f'max_len: {max_len}')
    train_inputs, train_masks, val_inputs, val_masks = get_inputs_and_masks(X, X_train, X_val, tokenizer, max_len)
    train_dataloader, val_dataloader = get_data_loader(train_inputs, train_masks, y_train, val_inputs, val_masks, y_val, batch_size=16)
    set_seed(42)    # Set seed for reproducibility
    bert_classifier, optimizer, scheduler = initialize_model(train_dataloader, device, epochs=epochs)
    print(20)
    train(bert_classifier, optimizer, scheduler, train_dataloader, val_dataloader, epochs=epochs, evaluation=True, device=device)
    print(22)
    accuracy, preds = predict(bert_classifier, X_test, y_test, tokenizer, max_len, device)
    return accuracy, bert_classifier, tokenizer, max_len, device


if __name__ == "__main__":
    dataset = pd.read_csv('/content/dataset.csv')
    dataset = dataset.dropna()
    dataset = dataset[dataset['sentiment'] != 'not_relevant']
    dataset["sentiment"] = dataset["sentiment"].astype(float).values
    dataset["sentiment"] = dataset["sentiment"].astype(float).values
    dataset["sentiment"][dataset["sentiment"] == 1] = 2
    dataset["sentiment"][dataset["sentiment"] == 0] = 1
    dataset["sentiment"][dataset["sentiment"] == -1] = 0

    X = dataset['text'].values
    y = dataset["sentiment"].astype(float).values

    train_val_size = 14900
    test_size = 100
    val_percentage = 0.01
    seed = 2022
    epochs = 1

    X_train_val = X[:train_val_size]
    y_train_val = y[:train_val_size]

    X_test = X[train_val_size : train_val_size + test_size]
    y_test = y[train_val_size : train_val_size + test_size]

    test_accuracy, bert_classifier, tokenizer, max_len, device = train_and_predict(X_train_val, y_train_val, X_test, y_test, val_percentage, epochs=epochs)
    print(test_accuracy)

    sample = "I'd be happy to help you with information on something that may be lost. "
    sample = "Please select one of the links I have provided below or you can try rephrasing your question."
    #sample = "I lost my card"
    #sample = "Where did you loose your card?"
    sample = "you can try rephrasing your question"
    accuracy, pred = predict(bert_classifier, [sample], np.array([0]).astype(np.float64), tokenizer, max_len, device)
    print(pred)