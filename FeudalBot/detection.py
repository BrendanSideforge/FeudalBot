import tensorflow as tf
import cv2

class AI:
    def __init__(self, model):
        self.model = model
        self.categories = ["Banana", "Banner", "Map"]

    def prepare(self, filepath):

        IMG_SIZE = 50
        img_array = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        try:
            new_array = cv2.resize(img_array, (IMG_SIZE, IMG_SIZE))
        except Exception as e:
            return print(e)
        return new_array.reshape(-1, IMG_SIZE, IMG_SIZE, 1)
        
    def predict(self, filepath):

        prediction = self.model.predict([self.prepare(filepath)])
        return self.categories[int(prediction[0][0])]