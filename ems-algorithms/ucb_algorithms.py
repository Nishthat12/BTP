#!/usr/bin/env python3
import numpy as np
import random
from collections import defaultdict

class L_EMS:
    """Latency-sensitive multi-server selection algorithm"""
    
    def __init__(self, servers, D=6):
        """Initialize the algorithm
        
        Args:
            servers: List of server names
            D: Number of data blocks needed
        """
        self.servers = servers
        self.D = D
        
        # Initialize service quality metrics
        self.omega = {server: 0.5 for server in servers}  # Initial service quality
        self.n = {server: 1 for server in servers}        # Number of selections
    
    def select_servers(self, round_num):
        """Select servers for a given round
        
        Args:
            round_num: Current round number
            
        Returns:
            List of selected servers
        """
        # Calculate UCB estimates
        ucb_estimates = {}
        for server in self.servers:
            ucb_estimate = self.omega[server] + np.sqrt((self.D + 1) * np.log(round_num) / self.n[server])
            ucb_estimates[server] = ucb_estimate
        
        # Sort servers by UCB estimate in descending order
        sorted_servers = sorted(ucb_estimates.items(), key=lambda x: x[1], reverse=True)
        
        # Select top D servers
        selected_servers = [server for server, _ in sorted_servers[:self.D]]
        
        return selected_servers
    
    def update(self, selected_servers, latencies):
        """Update service quality metrics based on observed latencies
        
        Args:
            selected_servers: List of selected servers
            latencies: Dictionary mapping servers to normalized latencies (0 to 1)
        """
        for server in selected_servers:
            if server in latencies:
                # Update service quality (omega)
                self.omega[server] = (self.omega[server] * self.n[server] + (1.0 - latencies[server])) / (self.n[server] + 1)
                # Increment selection count
                self.n[server] += 1

class D_EMS:
    """Deadline-aware multi-server selection algorithm"""
    
    def __init__(self, servers, D=6, H=9, V=100):
        """Initialize the algorithm
        
        Args:
            servers: List of server names
            D: Number of data blocks needed
            H: Threshold for average number of selected servers
            V: System parameter for Lyapunov optimization
        """
        self.servers = servers
        self.D = D
        self.H = H
        self.V = V
        
        # Initialize service quality metrics
        self.theta = {server: 0.5 for server in servers}  # Initial service quality
        self.n = {server: 1 for server in servers}        # Number of selections
        
        # Initialize virtual queue
        self.Q = 0
    
    def select_servers(self, round_num):
        """Select servers for a given round
        
        Args:
            round_num: Current round number
            
        Returns:
            List of selected servers
        """
        # Calculate UCB estimates
        ucb_estimates = {}
        for server in self.servers:
            ucb_estimate = min(self.theta[server] + np.sqrt(2 * np.log(round_num) / self.n[server]), 1.0)
            ucb_estimates[server] = ucb_estimate
        
        # Sort servers by UCB estimate in descending order
        sorted_servers = sorted(ucb_estimates.items(), key=lambda x: x[1], reverse=True)
        
        # Start with the top D servers (minimum required)
        selected_servers = [server for server, _ in sorted_servers[:self.D]]
        
        # Add more servers if beneficial based on Lyapunov optimization
        for server, ucb in sorted_servers[self.D:]:
            # Calculate the reward for adding this server
            reward = self.calculate_reward(selected_servers + [server], ucb_estimates)
            current_reward = self.calculate_reward(selected_servers, ucb_estimates)
            
            # If adding the server increases the objective, add it
            if self.V * (reward - current_reward) > self.Q:
                selected_servers.append(server)
            else:
                break
        
        return selected_servers
    
    def calculate_reward(self, servers, ucb_estimates):
        """Calculate the reward for a set of servers
        
        Args:
            servers: List of servers
            ucb_estimates: Dictionary mapping servers to UCB estimates
            
        Returns:
            Expected reward
        """
        # Probability of successfully downloading at least D video blocks
        # This is a simplified calculation for the simulation
        success_probs = [ucb_estimates[server] for server in servers]
        
        # Calculate the probability using a binomial distribution approximation
        if len(success_probs) < self.D:
            return 0.0
        
        # Sort probabilities in descending order
        sorted_probs = sorted(success_probs, reverse=True)
        
        # Take the D-th largest probability as the reward
        # (simplified from the full calculation in the paper)
        return sorted_probs[self.D-1]
    
    def update(self, selected_servers, successes):
        """Update service quality metrics based on observed successes
        
        Args:
            selected_servers: List of selected servers
            successes: Dictionary mapping servers to success indicators (0 or 1)
        """
        for server in selected_servers:
            if server in successes:
                # Update service quality (theta)
                self.theta[server] = (self.theta[server] * self.n[server] + successes[server]) / (self.n[server] + 1)
                # Increment selection count
                self.n[server] += 1
        
        # Update virtual queue
        self.Q = max(self.Q - self.H, 0) + len(selected_servers)
