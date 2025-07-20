import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime

# Create plots directory if it doesn't exist
os.makedirs('plots', exist_ok=True)

def load_data():
    """Load the data from CSV files"""
    try:
        message_log = pd.read_csv('server/data/message_log.csv')
        roster_performance = pd.read_csv('server/data/roster_performance.csv')
        command_delivery = pd.read_csv('server/data/command_delivery.csv')
        
        # Convert timestamp columns to datetime
        message_log['timestamp'] = pd.to_datetime(message_log['timestamp'])
        roster_performance['timestamp'] = pd.to_datetime(roster_performance['timestamp'])
        command_delivery['timestamp'] = pd.to_datetime(command_delivery['timestamp'])
        
        return message_log, roster_performance, command_delivery
    except FileNotFoundError:
        print("Data files not found. Please run the server first to collect data.")
        return None, None, None

def analyze_message_distribution(message_log):
    """Analyze the distribution of message types"""
    if message_log is None:
        return
    
    # Count messages by type
    msg_counts = message_log['message_type'].value_counts()
    
    # Create bar chart
    plt.figure(figsize=(10, 6))
    msg_counts.plot(kind='bar', color='skyblue')
    plt.title('Message Type Distribution')
    plt.xlabel('Message Type')
    plt.ylabel('Count')
    plt.tight_layout()
    plt.savefig('plots/message_distribution.png')
    
    # Print statistics
    print("Message Type Distribution:")
    print(msg_counts)
    print("\nPercentage:")
    print((msg_counts / msg_counts.sum() * 100).round(2))

def analyze_roster_performance(roster_performance):
    """Analyze the roster discovery performance"""
    if roster_performance is None:
        return
    
    # Calculate discovery rate
    roster_performance['discovery_rate'] = roster_performance['devices_discovered'] / roster_performance['devices_expected']
    roster_performance['discovery_rate'] = roster_performance['discovery_rate'].fillna(0)
    
    # Plot discovery rate over time
    plt.figure(figsize=(12, 6))
    plt.plot(roster_performance['timestamp'], roster_performance['discovery_rate'], 'b-', marker='o')
    plt.title('Device Discovery Rate Over Time')
    plt.xlabel('Timestamp')
    plt.ylabel('Discovery Rate')
    plt.ylim(0, 1.1)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('plots/discovery_rate.png')
    
    # Response delay analysis
    plt.figure(figsize=(12, 6))
    plt.hist(roster_performance['response_delay_ms'], bins=20, alpha=0.7, color='green')
    plt.title('Roster Response Delay Distribution')
    plt.xlabel('Response Delay (ms)')
    plt.ylabel('Frequency')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('plots/roster_delay.png')
    
    # Print statistics
    print("\nRoster Performance Statistics:")
    print(f"Average Discovery Rate: {roster_performance['discovery_rate'].mean():.2f}")
    print(f"Median Discovery Rate: {roster_performance['discovery_rate'].median():.2f}")
    print(f"Average Response Delay: {roster_performance['response_delay_ms'].mean():.2f} ms")
    print(f"Median Response Delay: {roster_performance['response_delay_ms'].median():.2f} ms")
    print(f"Standard Deviation of Delay: {roster_performance['response_delay_ms'].std():.2f} ms")
    
    # Calculate 95% confidence interval for response delay
    n = len(roster_performance)
    if n > 1:
        mean = roster_performance['response_delay_ms'].mean()
        std_err = roster_performance['response_delay_ms'].std() / np.sqrt(n)
        conf_interval = 1.96 * std_err  # 95% confidence interval
        print(f"95% Confidence Interval for Response Delay: {mean:.2f} ± {conf_interval:.2f} ms")

def analyze_command_delivery(command_delivery):
    """Analyze the command delivery performance"""
    if command_delivery is None:
        return
    
    # Filter for delivered commands with delay data
    delivered = command_delivery[command_delivery['delivered'] == True]
    delivered = delivered[delivered['delivery_delay_ms'] != 'None']
    delivered['delivery_delay_ms'] = delivered['delivery_delay_ms'].astype(float)
    
    if len(delivered) == 0:
        print("\nNo delivered commands with delay data found.")
        return
    
    # Plot delivery delay distribution
    plt.figure(figsize=(12, 6))
    plt.hist(delivered['delivery_delay_ms'], bins=20, alpha=0.7, color='orange')
    plt.title('Command Delivery Delay Distribution')
    plt.xlabel('Delivery Delay (ms)')
    plt.ylabel('Frequency')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('plots/delivery_delay.png')
    
    # Calculate delivery success rate
    total_commands = len(command_delivery)
    delivered_count = len(delivered)
    success_rate = delivered_count / total_commands if total_commands > 0 else 0
    
    # Calculate ACK rate
    ack_count = len(command_delivery[command_delivery['ack_received'] == True])
    ack_rate = ack_count / delivered_count if delivered_count > 0 else 0
    
    # Print statistics
    print("\nCommand Delivery Statistics:")
    print(f"Total Commands Sent: {total_commands}")
    print(f"Commands Successfully Delivered: {delivered_count}")
    print(f"Delivery Success Rate: {success_rate:.2%}")
    print(f"Commands with ACK: {ack_count}")
    print(f"ACK Rate: {ack_rate:.2%}")
    print(f"Average Delivery Delay: {delivered['delivery_delay_ms'].mean():.2f} ms")
    print(f"Median Delivery Delay: {delivered['delivery_delay_ms'].median():.2f} ms")
    print(f"Standard Deviation of Delay: {delivered['delivery_delay_ms'].std():.2f} ms")
    
    # Calculate 95% confidence interval for delivery delay
    n = len(delivered)
    if n > 1:
        mean = delivered['delivery_delay_ms'].mean()
        std_err = delivered['delivery_delay_ms'].std() / np.sqrt(n)
        conf_interval = 1.96 * std_err  # 95% confidence interval
        print(f"95% Confidence Interval for Delivery Delay: {mean:.2f} ± {conf_interval:.2f} ms")

def main():
    print("Loading data...")
    message_log, roster_performance, command_delivery = load_data()
    
    if message_log is None:
        return
    
    print("\nAnalyzing data...")
    
    # Analyze message distribution
    analyze_message_distribution(message_log)
    
    # Analyze roster performance
    analyze_roster_performance(roster_performance)
    
    # Analyze command delivery
    analyze_command_delivery(command_delivery)
    
    print(f"\nAnalysis complete. Plots saved to {os.path.abspath('plots/')} directory.")

if __name__ == "__main__":
    main()
