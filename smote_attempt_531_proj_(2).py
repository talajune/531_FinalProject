# -*- coding: utf-8 -*-
"""smote_attempt_531_proj (2).ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/141PRVpmRIC-9hPMdtXkcyXQnnNI81Y8C
"""

!pip install pyspark

import os
from google.colab import drive
drive.mount('/content/drive', force_remount=True)
#folder_path = '/content/drive/My Drive/531_Final_Project

!pip install xgboost

from pyspark import SparkContext, SparkConf
import sys
import csv
from itertools import islice, combinations
import time
import random
import itertools
import json
import xgboost as xgb
from xgboost import XGBRegressor
import numpy as np

if __name__ == '__main__':
  start_time = time.time()
  conf = SparkConf().setAppName('531_final_proj').setMaster('local[*]')
  sc = SparkContext.getOrCreate(conf=conf)
  sc.setSystemProperty('spark.driver.memory', '4g')
  sc.setSystemProperty('spark.executor.memory', '4g')
  sc.setLogLevel("ERROR")


lines = sc.textFile('/content/drive/My Drive/531_Final_Project/patients_data.csv')

# Retrieve the first line containing column names
column_names = lines.first()

rdd = lines.filter(lambda row: row != column_names).map(lambda row: row.split(','))

#first18_rdd = lines.filter(lambda row: row != column_names).map(lambda row: row.split(',')[1:18])

rdd.take(1)

pre_processed_rdd = rdd.filter(lambda row: all(row[index] != '' for index in [2, 3, 6, 12]))

# make column 2, 3 to float
def convert_columns_rdd(row):
    return row[:1] + [float(row[i]) if i in [2, 3] else row[i] for i in range(1, len(row))]

rdd = pre_processed_rdd.map(convert_columns_rdd)

# STRATIFIED SAMPLING
column_12_values = pre_processed_rdd.map(lambda row: row[12])
distribution = column_12_values.countByValue()

# To print the distribution
for value, count in distribution.items():
    print(f"Value: {value}, Count: {count}")

# keeping 20% of data
discharge_count = 391979
admit_count = 166013

total_count = discharge_count + admit_count

discharge_fraction_original = discharge_count / total_count
admit_fraction_original = admit_count / total_count

discharge_fraction_20 = discharge_fraction_original * 0.2
admit_fraction_20 = admit_fraction_original * 0.2

expected_sample_size_discharge = discharge_count * 0.2
expected_sample_size_admit = admit_count * 0.2

total_expected_sample_size = expected_sample_size_discharge + expected_sample_size_admit

(discharge_fraction_20, admit_fraction_20, expected_sample_size_discharge, expected_sample_size_admit, total_expected_sample_size)

pair_rdd = rdd.map(lambda row: (row[12], row))

fractions = {
    "Discharge": 0.14049627951655222,  # fraction for "Discharge"
    "Admit": 0.05950372048344779 # fraction for "Admit"
}

stratified_sample_rdd = pair_rdd.sampleByKey(False, fractions)

sample_count = stratified_sample_rdd.count()

for sample in stratified_sample_rdd.take(5):
    print(sample)

"""DATA PRE PROCESSING
DROP column 2 -- ESI, and make all NaN values in columns > 18 = 0 because they are medical and we assume not present binary
"""

og_stratified_rdd = stratified_sample_rdd.map(lambda kv: kv[1])

adjusted_rdd = og_stratified_rdd.map(lambda row: row[:18] + [0.0 if item == '' else item for item in row[18:]])

adjusted_rdd.take(1)

# change columns 2, 3, to floats
# make column 2, 3 to float
def convert_columns_rdd(row):
    return row[:1] + [float(row[i]) if i in [2, 3] else row[i] for i in range(1, len(row))]

adjusted_rdd = adjusted_rdd.map(convert_columns_rdd)

# TRAIN TEST SPLIT
# getting rid of index
# Use the map transformation to remove the first column from each row
preprocessed_rdd_no_first_column = adjusted_rdd.map(lambda row: row[1:])

train_rdd, test_rdd = preprocessed_rdd_no_first_column.randomSplit(weights=[0.7, 0.3], seed=42) # 70 / 30 split

# Label
X_train = train_rdd.map(lambda row: row[:10] + row[12:])
X_test = test_rdd.map(lambda row: row[:10] + row[12:])

y_train = train_rdd.map(lambda row: row[11]) # index 11 is discharge
y_test = test_rdd.map(lambda row: row[11])

"""ONE HOT ENCODING"""

# ONE HOT ENCODE X_train, X_test columns
# [0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

columns_to_encode = [0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] # check number


# Extract distinct values for each categorical column
distinct_values = {}
for col_index in columns_to_encode:
    distinct_values[col_index] = X_train.map(lambda row: row[col_index]).distinct().collect()

# Broadcast distinct values to all workers
distinct_values_bc = sc.broadcast(distinct_values)

# Function to one-hot encode a row
def one_hot_encode_row(row):
    encoded_row = []
    for col_index, value in enumerate(row):
        if col_index in distinct_values_bc.value:
            # If the column is categorical, create a one-hot encoded vector
            categories = distinct_values_bc.value[col_index]
            encoded_vector = [1 if category == value else 0 for category in categories]
            encoded_row.extend(encoded_vector)
        else:
            # If the column is not categorical, keep the original value
            encoded_row.append(value)
    return encoded_row

# Apply one-hot encoding to the entire RDD
X_train_encoded = X_train.map(one_hot_encode_row)



columns_to_encode = [0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]


# Extract distinct values for each categorical column
distinct_values = {}
for col_index in columns_to_encode:
    distinct_values[col_index] = X_test.map(lambda row: row[col_index]).distinct().collect()

# Broadcast distinct values to all workers
distinct_values_bc = sc.broadcast(distinct_values)

# Function to one-hot encode a row
def one_hot_encode_row(row):
    encoded_row = []
    for col_index, value in enumerate(row):
        if col_index in distinct_values_bc.value:
            # If the column is categorical, create a one-hot encoded vector
            categories = distinct_values_bc.value[col_index]
            encoded_vector = [1 if category == value else 0 for category in categories]
            encoded_row.extend(encoded_vector)
        else:
            # If the column is not categorical, keep the original value
            encoded_row.append(value)
    return encoded_row

# Apply one-hot encoding to the entire RDD
X_test_encoded = X_test.map(one_hot_encode_row)

# one hot encode y_train and y_test
y_train_encoded = y_train.map(lambda status: 1 if status == 'Admit' else 0)
y_test_encoded = y_test.map(lambda status: 1 if status == 'Admit' else 0)

# change everything to floats and not strings
def convert_row_to_floats(row):
    # Convert each element in the row to float if it is a number in string format
    new_row = []
    for item in row:
        try:
            # Attempt to convert to float
            new_row.append(float(item))
        except ValueError:
            # If conversion fails, keep the original item
            new_row.append(item)
    return new_row

# Apply the conversion function to each row in the RDD
X_train_encoded_floats = X_train_encoded.map(convert_row_to_floats)
X_test_encoded_floats =  X_test_encoded.map(convert_row_to_floats)
# Now X_train_encoded_floats RDD will have all possible string representations of numbers converted to floats

X_train = X_train_encoded_floats.collect()
X_test = X_test_encoded_floats.collect()

y_train = y_train_encoded.collect()
y_test = y_test_encoded.collect()

params = {
    'objective': 'binary:hinge',
    # Add other parameters here as needed
    'eval_metric': 'rmse',
}
xgb_model = xgb.XGBRegressor(**params)
xgb_model.fit(X_train, y_train)

X_train

import csv

def save_data_to_csv(data, filename):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        for row in data:
            if isinstance(row, int) or isinstance(row, float):  # Check if the element is an int or float
                writer.writerow([row])  # Convert int or float to a list
            else:
                writer.writerow(row)

# Save each dataset to a CSV file
save_data_to_csv(X_train, 'X_train2.csv')
save_data_to_csv(X_test, 'X_test2.csv')
save_data_to_csv(y_train, 'y_train2.csv')
save_data_to_csv(y_test, 'y_test2.csv')

!pip install fairlearn

preds = xgb_model.predict(X_test)

import numpy as np
from sklearn.metrics import mean_squared_error
print("RMSE : ", np.sqrt(mean_squared_error(y_test, preds)))

# Accuracy
from sklearn.metrics import accuracy_score
accuracy = accuracy_score(y_test, preds)
print("ACCURACY:", accuracy)

# Stat Parity

# by gender
# Example: Let's assume the sensitive attribute is gender, located at index 3
# and we're interested in creating two groups: males (1) and females (0)

# Extract the gender information from X_test and pair it with predictions from 'preds'
gender_and_preds = X_test_encoded_floats.map(lambda x: (x[5], x[6]))

# Group by gender and calculate the positive prediction rate for each gender
gender_positive_rates = gender_and_preds.groupByKey().mapValues(lambda preds: sum(preds) / len(preds))

# Collect the results
gender_positive_rates_collected = gender_positive_rates.collect()

# Calculate the statistical parity difference
statistical_parity_difference = abs(gender_positive_rates_collected[0][1] - gender_positive_rates_collected[1][1])

print("Statistical Parity Difference (Gender):", statistical_parity_difference)

# Equal Opprotunity Gender
#!pip install fairlearn
from fairlearn.metrics import equalized_odds_difference, equalized_odds_ratio

sens_data = X_test_encoded_floats.map(lambda x: (x[5], x[6]))  # Assuming gender is at index 4 and 5 in each data point

# Collect the results
sens_data_collected = sens_data.collect()
scalar_sens_data = [gender[0] for gender in sens_data_collected]

print("equalized odds difference gender", equalized_odds_difference(y_test,
                                preds,
                                sensitive_features=scalar_sens_data))

print("equalized odds ratio gender", equalized_odds_ratio(y_test,
                           preds,
                           sensitive_features=scalar_sens_data))

# Stat parity gender
from fairlearn.metrics import demographic_parity_ratio

sens_data = X_test_encoded_floats.map(lambda x: (x[5], x[6]))  # Gender ?

# Collect the results
sens_data_collected = sens_data.collect()
scalar_sens_data = [gender[0] for gender in sens_data_collected]

print(demographic_parity_ratio(y_test, preds, sensitive_features=scalar_sens_data))

# Stat Parity -> medicare vs medicaid (insurance status)

sens_data = X_test_encoded_floats.map(lambda x: (x[53:58]))  # INSURANCE STATUS

# Collect the results
sens_data_collected = sens_data.collect()

scalar_sens_data = [status[0] for status in sens_data_collected]

print("equalized odds insurance status",(equalized_odds_ratio(y_test,
                           preds,
                           sensitive_features=scalar_sens_data)))

print("stat parity insurance staus:", (demographic_parity_ratio(y_test, preds, sensitive_features=scalar_sens_data)))

# RACE: Stat Parity & equzlied odds -> race (11-17)
sens_data = X_test_encoded_floats.map(lambda x: (x[11:18]))  # RACE

# Collect the results
sens_data_collected = sens_data.collect()
scalar_sens_data = [race[0] for race in sens_data_collected]


print("equalized odds race:",(equalized_odds_ratio(y_test,
                           preds,
                           sensitive_features=scalar_sens_data)))

print("stat parity race:", (demographic_parity_ratio(y_test, preds, sensitive_features=scalar_sens_data)))
from fairlearn.metrics import demographic_parity_difference
# AGE
sens_data = X_test_encoded_floats.map(lambda x: x[4])  # AGE

# Collect the results
scalar_sens_data = sens_data.collect()
#scalar_sens_data = [age[0] for age in sens_data_collected]


print("equalized odds age:",(equalized_odds_ratio(y_test,
                           preds,
                           sensitive_features=scalar_sens_data)))

print("stat parity ratio age:", (demographic_parity_ratio(y_test, preds, sensitive_features=scalar_sens_data)))


print("stat parity difference age:", (demographic_parity_difference(y_test, preds, sensitive_features=scalar_sens_data)))

"""## RE-RUNNING MODEL WITH SMOTE"""

#sampling imbalance class with smoth + enn algorithm
from imblearn.combine import SMOTEENN
import collections
counter = collections.Counter(y_train)
print('Before', counter)
# oversampling the train dataset using SMOTE + ENN
smenn = SMOTEENN()
X_train_smenn, y_train_smenn = smenn.fit_resample (X_train, y_train)
counter = collections.Counter (y_train_smenn)
print('After', counter)

# smote results

# Equal Opprotunity Gender
#!pip install fairlearn
from fairlearn.metrics import equalized_odds_difference, equalized_odds_ratio

sens_data = X_test_encoded_floats.map(lambda x: (x[5], x[6]))  # Assuming gender is at index 4 and 5 in each data point

# Collect the results
sens_data_collected = sens_data.collect()
scalar_sens_data = [gender[0] for gender in sens_data_collected]

print("equalized odds difference gender", equalized_odds_difference(y_test,
                                y_pred,
                                sensitive_features=scalar_sens_data))

print("equalized odds ratio gender", equalized_odds_ratio(y_test,
                           y_pred,
                           sensitive_features=scalar_sens_data))

# Stat parity gender
from fairlearn.metrics import demographic_parity_ratio

sens_data = X_test_encoded_floats.map(lambda x: (x[5], x[6]))  # Gender ?

# Collect the results
sens_data_collected = sens_data.collect()
scalar_sens_data = [gender[0] for gender in sens_data_collected]

print(demographic_parity_ratio(y_test, y_pred, sensitive_features=scalar_sens_data))

# Stat Parity -> medicare vs medicaid (insurance status)

sens_data = X_test_encoded_floats.map(lambda x: (x[53:58]))  # INSURANCE STATUS

# Collect the results
sens_data_collected = sens_data.collect()

scalar_sens_data = [status[0] for status in sens_data_collected]

print("equalized odds insurance status",(equalized_odds_ratio(y_test,
                           y_pred,
                           sensitive_features=scalar_sens_data)))

print("stat parity insurance staus:", (demographic_parity_ratio(y_test, y_pred, sensitive_features=scalar_sens_data)))

# RACE: Stat Parity & equzlied odds -> race (11-17)
sens_data = X_test_encoded_floats.map(lambda x: (x[11:18]))  # RACE

# Collect the results
sens_data_collected = sens_data.collect()
scalar_sens_data = [race[0] for race in sens_data_collected]


print("equalized odds race:",(equalized_odds_ratio(y_test,
                           preds,
                           sensitive_features=scalar_sens_data)))

print("stat parity race:", (demographic_parity_ratio(y_test, y_pred, sensitive_features=scalar_sens_data)))
from fairlearn.metrics import demographic_parity_difference
# AGE
sens_data = X_test_encoded_floats.map(lambda x: x[4])  # AGE

# Collect the results
scalar_sens_data = sens_data.collect()
#scalar_sens_data = [age[0] for age in sens_data_collected]


print("equalized odds age:",(equalized_odds_ratio(y_test,
                           preds,
                           sensitive_features=scalar_sens_data)))

print("stat parity ratio age:", (demographic_parity_ratio(y_test, y_pred, sensitive_features=scalar_sens_data)))


print("stat parity difference age:", (demographic_parity_difference(y_test, y_pred, sensitive_features=scalar_sens_data)))



