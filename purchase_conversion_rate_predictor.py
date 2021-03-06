import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import textwrap

from keras.models import Model
from keras.layers import Input, Dense, Dropout, LSTM, Activation
from keras.layers.embeddings import Embedding
from keras.preprocessing import sequence
from keras.initializers import glorot_uniform

%matplotlib inline
np.random.seed(0)


MAX_RECORDS = 30

training_filename = "training.tsv"
train_df = pd.read_csv(training_filename,sep='\t')

test_filename = "test.tsv"
test_df = pd.read_csv(test_filename,sep='\t')

print(f'training shape   {train_df.shape}')
print(f'test shape       {test_df.shape}')

wrapper = textwrap.TextWrapper(width=110) 
string = wrapper.fill(text=f'{train_df.EmailOpen.unique()}')
print(string)

# make sure records ordered by user, date
train_df.sort_values(by=[train_df.columns[0],train_df.columns[1]], inplace=True)
test_df.sort_values(by=[test_df.columns[0],test_df.columns[1]], inplace=True)

def get_data_boundaries(df,column):
    num_unique_entries = 0

    stop_indices = []
    vals=[]
    col = df.loc[:,column]
    old_val = col[0]
    print(type(col))
    for record_idx in range(len((df.index)/3)):
        new_val = col[record_idx]
        if (new_val != old_val): 
            stop_indices.append(record_idx)
            vals.append(old_val)
            old_val = new_val 
            num_unique_entries += 1
    stop_indices.append(len(train_df.index))
    vals.append(old_val)
    return stop_indices, num_unique_entries, vals


train_stop_indices, train_num_unique_users, train_ids = get_data_boundaries (train_df,train_df.columns.values[0])
print ('train unique users',train_num_unique_users)

test_stop_indices, test_num_unique_users, test_ids = get_data_boundaries (test_df,test_df.columns[0])
print ('test unique users',test_num_unique_users)

dict_actions=dict([( 'FormSubmit',1), ('EmailOpen',2 ), ( 'Purchase',3), ( 'EmailClickthrough',4), ('CustomerSupport',5), ('PageView',6), ('WebVisit',7)]) 
print('done')

################

pd.set_option('display.max_rows', 200)
print(train_df.tail(200))
pd.reset_option('display.max_rows')

#################

all_actions = np.array(train_df['EmailOpen'].map(dict_actions)) 


y = np.zeros([train_num_unique_users], dtype='int64')
X= np.zeros([train_num_unique_users, MAX_RECORDS], dtype='int64' ) 

#extract all actions for a user_id 
rec_stop_i = 0
filtered_user_cnt = 0
stop_indices = train_stop_indices
user_ids = train_ids
num_unique_users = train_num_unique_users
filtered_user_ids=[]

print('got here')

for user_idx in range(num_unique_users):
    rec_start_i = rec_stop_i
    rec_stop_i = stop_indices[user_idx] 
    user_records = train_df.loc[rec_start_i:rec_stop_i-1]
    
    rows_to_delete = user_records[user_records['EmailOpen']=='CustomerSupport'].index
    tmp_records = user_records.drop(list(rows_to_delete))
    rows_to_delete = tmp_records[tmp_records['EmailOpen']=='Purchase'].index
    clean_user_records = tmp_records.drop(rows_to_delete)
    
    clean_user_records_len = min(len(clean_user_records.index), MAX_RECORDS)
    if clean_user_records_len:

        if sum( all_actions[rec_start_i:rec_stop_i] == dict_actions['Purchase']):
            y[filtered_user_cnt] = 1

        user_actions= np.array(clean_user_records['EmailOpen'].map(dict_actions))

        X[filtered_user_cnt,0:clean_user_records_len] = user_actions[0:clean_user_records_len]
        filtered_user_ids.append(user_ids[user_idx])
        filtered_user_cnt += 1
        
print('num of purchase users is  ' , sum(y[:filtered_user_cnt]),   'out of ', filtered_user_cnt, ' total remaining users' )
        

###########

# np.savetxt("future_purchasers.tsv",[X,filtered_user_ids,filtered_user_cnt], delimiter='\t')
f= open("future_purchasers.tsv","w+")
#f.write("This is line %d\r\n" % (i+1))

import pickle



#with open('data.pickle', 'wb+') as f:
    # Pickle the 'data' dictionary using the highest protocol available.
data=[X,filtered_user_ids,filtered_user_cnt]
  #  pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

with open('data.pickle', 'rb') as f:
    # The protocol version used is detected automatically, so we do not
    # have to specify it.
    new_data = pickle.load(f)
    
###############################

events_to_vec_map ={'0':[0,0,0,0,1],'1':[0,0,0,1,0],'2':[0,0,0,0,0],'3':[0,0,1,0,0],'4':[0,0,0,0,0],'5':[0,1,0,0,0],'6':[1,0,0,0,0]}

def pretrained_embedding_layer(word_to_vec_map, ):
    """
    Creates a Keras Embedding() layer 
    
    Arguments:
    events_to_vec_map -- dictionary mapping 
     -- dictionary mapping from words to their indices 

    Returns:
    embedding_layer -- pretrained layer Keras instance
    """
    
    NUM_EVENTS = 8   # len + 1   adding 1 to fit Keras embedding 
    EMB_DIM = 5  # events map one to one to 7 separate embedded dimensions -2 events not seen, -1 for Keras = 5

    # Initialize the embedding matrix 
    emb_matrix = np.zeros([NUM_EVENTS, EMB_DIM])
    
    for index in range(7):
        emb_matrix[index, :] = events_to_vec_map[str(index)]
    # Define Keras embedding layer with the correct output/input sizes
    embedding_layer = Embedding(NUM_EVENTS, EMB_DIM, trainable='False')

    # Build the embedding layer
    embedding_layer.build((None,))
    
    # Set the weights of the embedding layer to the embedding matrix.
    embedding_layer.set_weights([emb_matrix])
    
    return embedding_layer


def predict_V2(input_shape, event_to_vec_map ):
    """
    Function creating the predict-v2 model's graph.
    
    Arguments:
    input_shape -- MAX_RECORDS
    events_to_vec_map -- 5 dimensional user action
     -- dictionary mapping from events to their indices 

    Returns:
    model -- a model instance in Keras
    """
    
    # Define sentence_indices as the input of the graph, it should be of shape input_shape and dtype 'int32' (as it contains indices).
    sentence_indices = Input(input_shape,dtype='int32')
    
    # Create the embedding layer 
    embedding_layer = pretrained_embedding_layer(events_to_vec_map, )
    # Propagate through embedding layer
    embeddings = embedding_layer(sentence_indices) 
    
    # Propagate the embeddings through an LSTM layer with 16-dimensional hidden state
    X = LSTM(16,  return_sequences=True)(embeddings)
    # Add dropout with a probability of 0.5
    X = Dropout(rate=0.5)(X)
    # Propagate X trough another LSTM layer with 32-dimensional hidden state
    X = LSTM(32,)(X)
    # Add dropout with a probability of 0.5
    X = Dropout(0.5)(X)
    # Propagate X through a Dense layer 
    X = Dense(1,activation='sigmoid')(X)

    # Create Model instance which converts sentence_indices into X.
    model = Model(inputs=sentence_indices, outputs=X)

    return model

model = predict_V2((MAX_RECORDS,), events_to_vec_map )
model.summary()
print('99')
model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])

##############

remaining_users = 40000
remaining_users = remaining_users-(remaining_users %160)         

X_trunc = X[:remaining_users,:]
print('X trunc shape', X_trunc.shape)
y_trunc = y[:remaining_users]
 
    
FF= (np.array(range(remaining_users)))

X_train_actions = X_trunc[FF[(np.array(range(remaining_users))%5!=0)],:]
X_validate_actions = X_trunc[FF[(np.array(range(remaining_users))%5==0)],:]

Y_train_oh = y_trunc[FF[(np.array(range(remaining_users))%5!=0)]]
print(Y_train_oh[0:40])

#y=np.array(range(unique_users))
Y_validate_oh = y_trunc[FF[(np.array(range(remaining_users))%5==0)]]

print('y train one not dtype' , Y_train_oh.dtype)
print(' y validate oh data type', Y_validate_oh.dtype)

print(Y_train_oh.shape)
print(Y_validate_oh.shape)

model.fit(X_train_actions, Y_train_oh, epochs = 1, batch_size = 32, shuffle=True)

#####################

loss, acc = model.evaluate(X_validate_actions, Y_validate_oh)
#print(X_validate_actions[0:100], Y_validate_oh[0:100])
print("Validation accuracy = ", acc)

pred = model.predict(X_validate_actions)


#######################


#fmt = '{:<8}{}{}{width:6.4}'
#print(fmt.format( 'index', '30 action values', 'purchase label','pred'))
i=0
while i < 100:
    #(action_array, purchase) in enumerate(zip(X_validate_actions[:], Y_validate_oh)):
#    print(fmt.format(i, X_validate_actions[i,:], Y_validate_oh[i],pred[i,0]))

    print(f'{i:<8}  {X_validate_actions[i,:]}   {Y_validate_oh[i]}    {pred[i,0]}'  )
    i+=1
#verify = pd.read_csv("future_purchasers.tsv",sep='\t')
#print(verify)

############

pred = model.predict(X_train_indices)
sorted_set=sorted(zip(pred, list(train_unique_users)),reverse=True)
sorted_pred, sorted_user_ids= (*zip(sorted_set))
print(sorted_pred[0:100])
np.savetxt("future_purchasers.tsv",sorted_pred[0:1000], delimiter='\t')


################

sorted_set=sorted(zip(pred, list(train_unique_ids)),reverse=True)
sorted_pred, sorted_user_ids= (*zip(sorted_set))
print(sorted_pred[0:100])
np.savetxt("future_purchasers.tsv",sorted_pred[0:1000], delimiter='\t')

###########
sorted_pred=sorted(zip(pred),reverse=True)

print(pred[0:1])

pd.set_option('display.max_rows', 500)
print(train[150:150])
