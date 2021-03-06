import argparse
import csv

from imbDRL.agents.ddqn import TrainDDQN
from imbDRL.data import get_train_test_val
from imbDRL.metrics import classification_metrics, network_predictions
from imbDRL.utils import imbalance_ratio
from sklearn.model_selection import train_test_split
from tensorflow import keras
from tensorflow.keras.layers import Dense
from tqdm import tqdm

from histology_preprocessing import read_dataframe

parser = argparse.ArgumentParser(description="Generates dataset based on Path argument.")
parser.add_argument("imagepath", metavar="Path", type=str, nargs="?", default="./data/hist", help="The path to the folder containing PNGs.")
parser.add_argument("csvpath", metavar="Path", type=str, nargs="?", default="./data/AE_20201412.csv", help="The path to the csv-file.")
args = parser.parse_args()

episodes = 12_000  # Total number of episodes
warmup_steps = 10_000  # Amount of warmup steps to collect data with random policy
memory_length = 10_000  # Max length of the Replay Memory
batch_size = 32
collect_steps_per_episode = 100
collect_every = 100

target_update_period = 400  # Period to overwrite the target Q-network with the default Q-network
target_update_tau = 1  # Soften the target model update
n_step_update = 4

layers = [Dense(40, activation="relu", input_shape=(None, 2, )),
          Dense(40, activation="relu"),
          Dense(2, activation=None)]

learning_rate = 0.00025  # Learning rate
gamma = 0.0  # Discount factor
min_epsilon = 0.01  # Minimal and final chance of choosing random action
decay_episodes = 10_000  # Number of episodes to decay from 1.0 to `min_epsilon`

min_class = [1]  # Labels of the minority classes
maj_class = [0]  # Labels of the majority classes

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
# print(f"{df.sample(3)}\n")

# Ensure same train/test split every time
_X_train, _X_test, _y_train, _y_test = train_test_split(df[["Age", "arteryop"]].to_numpy(), y, test_size=0.2, random_state=42, stratify=y)
fp_dqn = "./results/histology/dqn_struct.csv"
fieldnames = ("Gmean", "F1", "Precision", "Recall", "TP", "TN", "FP", "FN")

# Create empty files
with open(fp_dqn, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()

# Run the model ten times
for _ in tqdm(range(10)):
    # New train-test split
    X_train, y_train, X_test, y_test, X_val, y_val = get_train_test_val(_X_train, _y_train, _X_test, _y_test, min_class, maj_class,
                                                                        val_frac=0.2, print_stats=False)
    keras.backend.clear_session()
    model = TrainDDQN(episodes, warmup_steps, learning_rate, gamma, min_epsilon, decay_episodes, target_update_period=target_update_period,
                      target_update_tau=target_update_tau, batch_size=batch_size, collect_steps_per_episode=collect_steps_per_episode,
                      memory_length=memory_length, collect_every=collect_every, n_step_update=n_step_update, progressbar=False)

    model.compile_model(X_train, y_train, layers)
    model.train(X_val, y_val, "F1")

    # Predictions of model for `X_test`
    best_network = model.load_model(fp=model.model_path)
    y_pred = network_predictions(best_network, X_test)
    dqn_stats = classification_metrics(y_test, y_pred)

    # Write current DQN run to `fp_dqn`
    with open(fp_dqn, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow(dqn_stats)
