import argparse

import numpy as np
from imbDRL.metrics import classification_metrics
from imbDRL.utils import imbalance_ratio
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from histology_preprocessing import read_dataframe

parser = argparse.ArgumentParser(description="Load pandas DataFrame from csv-file.")
parser.add_argument("csvpath", metavar="Path", type=str, nargs="?", default="./data/AE_20201412.csv", help="The path to the csv-file.")
args = parser.parse_args()

df = read_dataframe(args.csvpath)
df = df[(df.Gender == "1") & (df.Hospital == "2")]
df = df[(df.restenos != -1) & (df.restenos != 2)]
y = df["restenos"].to_numpy()
print(f"Imbalance ratio: {imbalance_ratio(y):.4f}\nRestenos:\n{df['restenos'].value_counts().to_string()}\n")

df.drop(columns=["restenos", "Gender", "Hospital"], inplace=True)
df["month"] = df["dateok"].dt.month
df["dateok"] = df["dateok"].dt.year
df = df.reset_index(drop=True)  # Drop study number
df = df.astype("int32")
df = (df - df.min()) / (df.max() - df.min())  # Normalization
print(f"{df.sample(3)}\n")

X_train, X_test, y_train, y_test = train_test_split(df[["Age", "arteryop"]].to_numpy(), y, test_size=0.2, random_state=42,
                                                    stratify=y)  # Ensure same train/test split every time


def uniform_baseline(X, y):
    uniform_clf = DummyClassifier(strategy="uniform")
    uniform_clf.fit(X, y)
    y_pred = uniform_clf.predict(X)
    return classification_metrics(y, y_pred)


def minority_baseline(X, y):
    most_frequent_clf = DummyClassifier(strategy="constant", constant=1)
    most_frequent_clf.fit(X, y)
    y_pred = most_frequent_clf.predict(X)
    return classification_metrics(y, y_pred)


def lin_reg(X_train, y_train, X_test, y_test):
    lr_clf = LogisticRegression(class_weight="balanced").fit(X_train, y_train)
    y_pred = lr_clf.predict(X_test)
    return classification_metrics(y_test, y_pred)


stats_uniform = []
stats_minority = []
stats_lr = []
for _ in range(100):
    stats_uniform.append(uniform_baseline(X_test, y_test))
    stats_minority.append(minority_baseline(X_test, y_test))
    stats_lr.append(lin_reg(X_train, y_train, X_test, y_test))

for lst in stats_uniform, stats_minority, stats_lr:
    for metric in "F1", "Precision", "Recall":
        print(f"{metric}: {np.round(np.mean([d[metric] for d in lst]), 3)} ± {np.round(np.std([d[metric] for d in lst]), 3)}")
    print()
