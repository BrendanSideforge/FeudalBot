import os
import random
import pickle

import numpy as np
import cv2

class BasicTraining:
    def __init__(self, data_dir, categories, img_size):
        self.data_dir = data_dir
        self.categories = categories
        self.img_size = img_size
        self.training_data = []

    def create_training_data(self):

        for category in self.categories:
            path = os.path.join(self.data_dir, category)
            class_num = self.categories.index(category)
            print(f"{category}: {len(os.listdir(path))}")
            for img in os.listdir(path):
                try:
                    img_array = cv2.imread(os.path.join(path, img), cv2.IMREAD_GRAYSCALE)
                    new_array = cv2.resize(img_array, (self.img_size, self.img_size))
                    self.training_data.append([new_array, class_num])
                except:
                    pass
        
        print(f"Successfully created training data. ({len(self.training_data)})")

Trainer = BasicTraining("Training/Datasets/Images", ["Banana", "Banner", "Map"], 50)
Trainer.create_training_data()
training_data = Trainer.training_data
random.shuffle(training_data)

X = []
y = []

for features, label in training_data:
    X.append(features)
    y.append(label)

X = np.array(X).reshape(-1, Trainer.img_size, Trainer.img_size, 1)
X_pickle_out = open("Training/X.pickle", "wb")
pickle.dump(X, X_pickle_out)
X_pickle_out.close()

y_pickle_out = open("Training/y.pickle", "wb")
pickle.dump(y, y_pickle_out)
y_pickle_out.close()