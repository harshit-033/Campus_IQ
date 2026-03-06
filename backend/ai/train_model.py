import pandas as pd
from sklearn.linear_model import LinearRegression
import joblib


data = {
    "participant_limit": [100,200,300,150,250,120],
    "fee":[0,100,200,50,150,0],
    "registrations":[80,150,210,120,200,100],
    "attendance":[70,130,180,100,170,90]
}

df = pd.DataFrame(data)

X = df[["participant_limit","fee","registrations"]]
y = df["attendance"]

model = LinearRegression()
model.fit(X,y)

joblib.dump(model,"attendance_model.pkl")

print("Model trained successfully")