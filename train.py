from dataset import FPC
from model.simulator import Simulator
import torch
from utils.noise import get_velocity_noise
import time
from utils.utils import NodeType
from torch_geometric.loader import DataLoader
import torch_geometric.transforms as T

dataset_dir = "/home/jlx/dataset/data"
batch_size = 8
noise_std=2e-2
print_batch = 10
save_batch = 200
warmup_batch = 1000

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
simulator = Simulator(message_passing_num=15, node_input_size=11, edge_input_size=3, device=device)
optimizer= torch.optim.Adam(simulator.parameters(), lr=1e-4)
print('Optimizer initialized')


def train(model:Simulator, dataloader, optimizer):

    for batch_index, graph in enumerate(dataloader):
        t1 = time.time()
        graph = transformer(graph)
        graph = graph.cuda()

        node_type = graph.x[:, 0] #"node_type, cur_v, pressure, time"
        velocity_sequence_noise = get_velocity_noise(graph, noise_std=noise_std, device=device)
        predicted_acc, target_acc = model(graph, velocity_sequence_noise)

        mask = torch.logical_or(node_type==NodeType.NORMAL, node_type==NodeType.OUTFLOW)
        errors = ((predicted_acc - target_acc)**2)[mask]

        loss = torch.mean(errors)

        if batch_index > warmup_batch:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        t2 = time.time()
        samples_per_second = 1/(t2 - t1) * batch_size

        if batch_index % print_batch == 0:
            print('%d step, loss %.2e'%(batch_index, loss.item()))
            print('%.1f samples per second'%samples_per_second)
        
        if batch_index % save_batch == 0:
            model.save_checkpoint()

if __name__ == '__main__':

    dataset_fpc = FPC(dataset_dir=dataset_dir, split='train', max_epochs=50)
    train_loader = DataLoader(dataset=dataset_fpc, batch_size=batch_size, num_workers=4, prefetch_factor=2)
    transformer = T.Compose([T.FaceToEdge(), T.Cartesian(norm=False), T.Distance(norm=False)])
    train(simulator, train_loader, optimizer)
