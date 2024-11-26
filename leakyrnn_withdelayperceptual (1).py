# -*- coding: utf-8 -*-
"""LeakyRNN_withDelayPerceptual.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Cdo-t-568xL0AOUGIyVEQt5jH-Z6MJjO

#Training RNNs on cognitive tasks
"""

# # Uninstall the current Gym version
# !pip uninstall -y gym

# # Install Gym version 0.23.1
# !pip install gym==0.23.1

# # Restart the runtime after installation (necessary in some environments like Colab)
# import os
# os._exit(00)

"""### Installing and importing relevant packages"""

# Commented out IPython magic to ensure Python compatibility.
# Install neurogym to use cognitive tasks
! git clone https://github.com/neurogym/neurogym.git
# %cd neurogym/
! pip install -e .

# Import common packages
import numpy as np
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
import time

"""## Defining a recurrent neural network"""

class LeakyRNN(nn.Module):
    """Leaky RNN.

    Parameters:
        input_size: Number of input neuron at each time step
        hidden_size: Number of hidden neurons (units) in the RNN
        dt: discretization time step in ms.
            If None, dt equals time constant tau.

            The new activity uses 1-alpha which determines how much of the old
            activity is remembered in the new time point, and it uses alpha to
            determine the update. This gives this model its leaky nature, that
            allows some previous information to decay over time.
            Alpha is dt/tau.

    Inputs:
        input: tensor of shape (seq_len, batch, input_size)
        hidden: tensor of shape (batch, hidden_size), initial hidden activity
            if None, hidden is initialized through self.init_hidden()

    Outputs:
        output: tensor of shape (seq_len, batch, hidden_size)
        hidden: tensor of shape (batch, hidden_size), final hidden activity
    """

    def __init__(self, input_size, hidden_size, dt=None, **kwargs):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.tau = 100
        if dt is None:
            alpha = 1
        else:
            alpha = dt / self.tau
        self.alpha = alpha

        self.input2h = nn.Linear(input_size, hidden_size)
        self.h2h = nn.Linear(hidden_size, hidden_size)

    def init_hidden(self, input_shape):
        return torch.zeros(batch_size, self.hidden_size)

    def recurrence(self, input, hidden):
        """Run network for one time step.

        Inputs:
            input: tensor of shape (batch, input_size)
            hidden: tensor of shape (batch, hidden_size)

        Outputs:
            h_new: tensor of shape (batch, hidden_size),
                network activity at the next time step
        """
        h_new = torch.relu(self.input2h(input) + self.h2h(hidden))
        h_new = hidden * (1 - self.alpha) + h_new * self.alpha
        return h_new

    def forward(self, input, hidden=None):
        """Propogate input through the network."""

        # If hidden activity is not provided, initialize it
        if hidden is None:
            hidden = self.init_hidden(input.size(1))

        # Loop through time
        output = []
        for i in range(input.size(0)):
            hidden = self.recurrence(input[i], hidden)
            output.append(hidden)

        # Stack together output from all time steps
        output = torch.stack(output, dim=0)  # (seq_len, batch, hidden_size)
        return output, hidden


class RNNNet(nn.Module):
    """Recurrent network model.

    Parameters:
        input_size: int, input size
        hidden_size: int, hidden size
        output_size: int, output size

    Inputs:
        x: tensor of shape (Seq Len, Batch, Input size)

    Outputs:
        out: tensor of shape (Seq Len, Batch, Output size)
        rnn_output: tensor of shape (Seq Len, Batch, Hidden size)
    """
    def __init__(self, input_size, hidden_size, output_size, **kwargs):
        super().__init__()

        # Leaky RNN
        self.rnn = LeakyRNN(input_size, hidden_size, **kwargs)

        # Add an output layer
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        rnn_output, _ = self.rnn(x)
        out = self.fc(rnn_output)
        return out, rnn_output

"""Let's determine the dimensions of its inputs and outputs."""

batch_size = 16
seq_len = 20  # sequence length
input_size = 5  # input dimension

# Make some random inputs
input_rnn = torch.rand(seq_len, batch_size, input_size)

# Make network of 100 hidden units and 10 output units
rnn = RNNNet(input_size=input_size, hidden_size=100, output_size=10)

# Run the sequence through the network
out, rnn_output = rnn(input_rnn)

print('Input of shape =', input_rnn.shape)
print('Output of shape =', out.shape)

"""## Defining a simple cognitive task

Here we use the neurogym package to make a simple "perceptual decision making Delay Response" task. Let us install the package first. NeuroGym is a curated collection of neuroscience tasks with a common interface.

The code provided below defines a custom environment, PerceptualDecisionMakingDelayResponse, using neurogym. In this task an agent have to integrate two stimuli and report which one is larger on average after a delay.
"""

# @title importing neurogym
import neurogym as ngym

# Canned environment from neurogym

task_name = 'PerceptualDecisionMakingDelayResponse-v0'
# @title importing neurogym
import neurogym as ngym

# Canned environment from neurogym

task_name = 'PerceptualDecisionMakingDelayResponse-v0'
timing= {
     'fixation': ('choice', (50, 100, 200, 400)),
     'stimulus': ('choice', (100, 200, 400, 800)),
     'delay': ('choice', (100, 200, 400, 800)),
     }


# Importantly, we set discretization time step for the task as well
kwargs = {'dt': 20, 'timing':timing}

"""For **supervised learning**, we need a dataset that returns (input, target output pairs)."""

# Make supervised dataset
seq_len = 100
batch_size = 16
dataset = ngym.Dataset(task_name, env_kwargs=kwargs, batch_size=batch_size, seq_len=seq_len)
env = dataset.env

# Generate one batch of data when called
inputs, target = dataset()
inputs = torch.from_numpy(inputs).type(torch.float)

input_size = env.observation_space.shape[0]
output_size = env.action_space.n

print('Input has shape (SeqLen, Batch, Dim) =', inputs.shape)
print('Target has shape (SeqLen, Batch) =', target.shape)
print(target[:, 0])

"""## Network Training

Let's now train the network to perform the task.
"""

import logging
logging.getLogger('matplotlib.font_manager').setLevel(level=logging.CRITICAL)
# Instantiate the network and print information
hidden_size = 128
net = RNNNet(input_size=input_size, hidden_size=hidden_size,
             output_size=output_size, dt=env.dt)
print(net)

def train_model(net, dataset):
    """Simple helper function to train the model.

    Args:
        net: a pytorch nn.Module module
        dataset: a dataset object that when called produce a (input, target output) pair

    Returns:
        net: network object after training
    """
    # Use Adam optimizer
    optimizer = optim.Adam(net.parameters(), lr=0.0005)
    criterion = nn.CrossEntropyLoss()

    loss_values = []  # List to store loss values
    running_loss = 0
    running_acc = 0
    start_time = time.time()
    # Loop over training batches
    print('Training network...')
    for i in range(5000):
        # Generate input and target, convert to pytorch tensor
        inputs, labels = dataset()
        inputs = torch.from_numpy(inputs).type(torch.float)
        labels = torch.from_numpy(labels.flatten()).type(torch.long)

        # boiler plate pytorch training:
        optimizer.zero_grad()   # zero the gradient buffers
        output, _ = net(inputs)
        # Reshape to (SeqLen x Batch, OutputSize)
        output = output.view(-1, output_size)
        loss = criterion(output, labels)
        loss.backward()
        optimizer.step()    # Does the update

        # Compute the running loss every 100 steps
        running_loss += loss.item()
        if i % 100 == 99:
            running_loss /= 100
            print('Step {}, Loss {:0.4f}, Time {:0.1f}s'.format(
                i+1, running_loss, time.time() - start_time))
            loss_values.append(running_loss)  # Append loss here
            running_loss = 0
    return net, loss_values

net, loss_values = train_model(net, dataset)

# Plotting the learning curve
plt.figure(figsize=(10,5))
plt.title("Learning Curve")
plt.plot(loss_values, label='Loss')
plt.xlabel("Steps")
plt.ylabel("Loss")
plt.legend()
plt.show()

import torch
import torch.optim as optim
import torch.nn as nn
import time
import logging
logging.getLogger('matplotlib.font_manager').setLevel(level=logging.CRITICAL)
import matplotlib.pyplot as plt

# Assuming the RNNNet class and other parts are defined as before.

def train_model(net, dataset):
    """Simple helper function to train the model.

    Args:
        net: a pytorch nn.Module module
        dataset: a dataset object that when called produce a (input, target output) pair

    Returns:
        net: network object after training
        performance: List of performance values at each step
    """
    # Use Adam optimizer
    optimizer = optim.Adam(net.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()

    running_loss = 0
    performance = []  # To store performance at each step (accuracy)
    start_time = time.time()

    # Loop over training batches
    print('Training network...')
    for i in range(5000):
        # Generate input and target, convert to pytorch tensor
        inputs, labels = dataset()
        inputs = torch.from_numpy(inputs).type(torch.float)
        labels = torch.from_numpy(labels.flatten()).type(torch.long)

        # Reset gradients
        optimizer.zero_grad()

        # Forward pass
        output, _ = net(inputs)

        # Reshape to (SeqLen x Batch, OutputSize)
        output = output.view(-1, output_size)

        # Compute loss
        loss = criterion(output, labels)
        loss.backward()
        optimizer.step()  # Updates the weights

        # Compute running loss every 100 steps
        running_loss += loss.item()
        if i % 100 == 99:
            running_loss /= 100
            print(f'Step {i+1}, Loss {running_loss:.4f}, Time {time.time() - start_time:.1f}s')
            running_loss = 0

        # Compute accuracy for current batch (every step)
        with torch.no_grad():
            # Get predicted labels
            _, predicted = torch.max(output, 1)
            correct = (predicted == labels).sum().item()
            accuracy = correct / labels.size(0)

        # Store accuracy at this step
        performance.append(accuracy)

    return net, performance

# Instantiate the network
hidden_size = 128
net = RNNNet(input_size=input_size, hidden_size=hidden_size, output_size=output_size, dt=env.dt)
print(net)

# Train the model and track performance
net, performance = train_model(net, dataset)

# Plot performance
plt.figure(figsize=(10, 6))
plt.plot(range(1, 5001), performance)  # X-axis: steps, Y-axis: performance (accuracy)
plt.xlabel('Training Steps')
plt.ylabel('Performance (Accuracy)')
plt.title('Training Performance Over Time')
plt.grid(True)
plt.show()

"""## Testing the network

Here we run the network after training, record activity, and compute performance. We will explicitly loop through individual trials, so we can log the information and compute the performance of each trial.
"""

# Reset environment
env = dataset.env
env.reset(no_step=True)

# Initialize variables for logging
perf = 0
activity_dict = {}  # recording activity
trial_infos = {}  # recording trial information


num_trial = 200
for i in range(num_trial):
    # Neurogym boiler plate
    # Sample a new trial
    trial_info = env.new_trial()
    # Observation and groud-truth of this trial
    ob, gt = env.ob, env.gt
    # Convert to numpy, add batch dimension to input
    inputs = torch.from_numpy(ob[:, np.newaxis, :]).type(torch.float)

    # Run the network for one trial
    # inputs (SeqLen, Batch, InputSize)
    # action_pred (SeqLen, Batch, OutputSize)
    action_pred, rnn_activity = net(inputs)

    # Compute performance
    # First convert back to numpy
    action_pred = action_pred.detach().numpy()[:, 0, :]
    # Read out final choice at last time step
    choice = np.argmax(action_pred[-1, :])
    # Compare to ground truth
    correct = choice == gt[-1]


    # Record activity, trial information, choice, correctness
    rnn_activity = rnn_activity[:, 0, :].detach().numpy()
    activity_dict[i] = rnn_activity
    trial_infos[i] = trial_info  # trial_info is a dictionary
    trial_infos[i].update({'correct': correct})


# Print information for sample trials
for i in range(10):
    print('Trial ', i, trial_infos[i])

print('Average performance', np.mean([val['correct'] for val in trial_infos.values()]))

"""# Plot the network's activity in PCA
Next we will analyze the network by plotting its activity in PCA space. Each trajectory in the PC-space would correspond to a single trial.
"""

# Apply PCA, boilerplate sklearn
from sklearn.decomposition import PCA

# Concatenate activity for PCA
activity = np.concatenate(list(activity_dict[i] for i in range(num_trial)), axis=0)
print('Shape of the neural activity: (Time points, Neurons): ', activity.shape)

pca = PCA(n_components=2)
pca.fit(activity)  # activity (Time points, Neurons)
activity_pc = pca.transform(activity)  # transform to low-dimension
print('Shape of the projected activity: (Time points, PCs): ', activity_pc.shape)

# Project each trial and visualize activity

import matplotlib.pyplot as plt


# Plot all trials in ax1, plot fewer trials in ax2
fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True, sharex=True, figsize=(6, 3))

for i in range(100):
    # Transform and plot each trial
    activity_pc = pca.transform(activity_dict[i])  # (Time points, PCs)

    trial = trial_infos[i]
    color = 'red' if trial['ground_truth'] == 1 else 'blue'

    _ = ax1.plot(activity_pc[:, 0], activity_pc[:, 1], 'o-', color=color)
    if i < 3:
        _ = ax2.plot(activity_pc[:, 0], activity_pc[:, 1], 'o-', color=color)

    # Plot the beginning of a trial with a special symbol
    _ = ax1.plot(activity_pc[0, 0], activity_pc[0, 1], '^', color='black')

ax1.set_title('{:d} Trials'.format(100))
ax2.set_title('{:d} Trials'.format(3))
ax1.set_xlabel('PC 1')
ax1.set_ylabel('PC 2')

"""# Plot neural activity from sample trials"""

# @title Plot neural activity from sample trials
import logging
logging.getLogger('matplotlib.font_manager').setLevel(level=logging.CRITICAL)


import matplotlib.pyplot as plt

trial = 2

plt.figure()
_ = plt.plot(activity_dict[trial])

plt.xlabel('Time step')
plt.ylabel('Activity')