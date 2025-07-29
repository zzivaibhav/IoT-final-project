import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Load your experimental data
def load_data(csv_file):
    """Load and clean the experimental data"""
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def analyze_roster_accuracy(df):
    """Analyze roster discovery accuracy"""
    print("=== ROSTER DISCOVERY ACCURACY ===")
    
    # Get DISCOVER and ROSTER pairs
    discover_msgs = df[df['message_type'] == 'DISCOVER']
    roster_msgs = df[df['message_type'] == 'ROSTER']
    
    print(f"Total DISCOVER requests: {len(discover_msgs)}")
    print(f"Total ROSTER responses: {len(roster_msgs)}")
    
    # Calculate success rate
    roster_success_rate = len(roster_msgs) / len(discover_msgs) * 100 if len(discover_msgs) > 0 else 0
    print(f"Roster response rate: {roster_success_rate:.1f}%")
    
    # Analyze roster contents (devices found vs expected)
    # Assuming you have 2 devices, so expect 1 other device in roster
    expected_devices = 1  # Adjust based on your setup
    
    successful_rosters = roster_msgs[roster_msgs['success'] == True]
    print(f"Successful roster deliveries: {len(successful_rosters)}")
    
    return roster_success_rate

def analyze_delivery_success(df):
    """Analyze command delivery success rates"""
    print("\n=== COMMAND DELIVERY SUCCESS ===")
    
    command_msgs = df[df['message_type'] == 'COMMAND']
    ack_msgs = df[df['message_type'] == 'ACK']
    
    print(f"Total COMMAND messages sent: {len(command_msgs)}")
    print(f"Total ACK messages received: {len(ack_msgs)}")
    
    # Calculate delivery success rate
    delivery_success_rate = len(ack_msgs) / len(command_msgs) * 100 if len(command_msgs) > 0 else 0
    print(f"Command delivery success rate: {delivery_success_rate:.1f}%")
    
    # Success by spreading factor
    if 'spreading_factor' in df.columns:
        sf_success = command_msgs.groupby('spreading_factor').size()
        print(f"\nCommands by Spreading Factor:")
        for sf, count in sf_success.items():
            if sf:  # Only show non-empty SF values
                sf_acks = len(ack_msgs[ack_msgs['spreading_factor'] == sf])
                sf_rate = sf_acks / count * 100 if count > 0 else 0
                print(f"  {sf}: {sf_rate:.1f}% ({sf_acks}/{count})")
    
    return delivery_success_rate

def analyze_end_to_end_delays(df):
    """Analyze end-to-end delays"""
    print("\n=== END-TO-END DELAY ANALYSIS ===")
    
    # Get ACK messages with delays
    ack_with_delays = df[(df['message_type'] == 'ACK') & (df['end_to_end_delay_ms'].notna())]
    
    if len(ack_with_delays) == 0:
        print("No end-to-end delay data available")
        return None
    
    delays = ack_with_delays['end_to_end_delay_ms'].astype(float) / 1000  # Convert to seconds
    
    print(f"Number of complete cycles: {len(delays)}")
    print(f"Mean delay: {delays.mean():.1f} seconds")
    print(f"Median delay: {delays.median():.1f} seconds")
    print(f"Std deviation: {delays.std():.1f} seconds")
    print(f"Min delay: {delays.min():.1f} seconds")
    print(f"Max delay: {delays.max():.1f} seconds")
    
    # 95% confidence interval
    confidence_interval = stats.t.interval(0.95, len(delays)-1, 
                                         loc=delays.mean(), 
                                         scale=stats.sem(delays))
    print(f"95% Confidence Interval: [{confidence_interval[0]:.1f}, {confidence_interval[1]:.1f}] seconds")
    
    # Delay by spreading factor
    if 'spreading_factor' in ack_with_delays.columns:
        print(f"\nDelay by Spreading Factor:")
        for sf in ack_with_delays['spreading_factor'].unique():
            if sf and str(sf) != 'nan':
                sf_delays = delays[ack_with_delays['spreading_factor'] == sf]
                if len(sf_delays) > 0:
                    print(f"  {sf}: {sf_delays.mean():.1f}s ± {sf_delays.std():.1f}s (n={len(sf_delays)})")
    
    return delays

def analyze_rssi_snr(df):
    """Analyze RSSI and SNR statistics"""
    print("\n=== SIGNAL QUALITY ANALYSIS ===")
    
    # Filter out non-numeric RSSI/SNR values
    numeric_data = df[df['rssi'].notna() & df['snr'].notna()]
    
    if len(numeric_data) == 0:
        print("No RSSI/SNR data available")
        return
    
    rssi_values = pd.to_numeric(numeric_data['rssi'], errors='coerce').dropna()
    snr_values = pd.to_numeric(numeric_data['snr'], errors='coerce').dropna()
    
    if len(rssi_values) > 0:
        print(f"RSSI: {rssi_values.mean():.1f} ± {rssi_values.std():.1f} dBm (n={len(rssi_values)})")
        print(f"RSSI range: [{rssi_values.min():.1f}, {rssi_values.max():.1f}] dBm")
    
    if len(snr_values) > 0:
        print(f"SNR: {snr_values.mean():.1f} ± {snr_values.std():.1f} dB (n={len(snr_values)})")
        print(f"SNR range: [{snr_values.min():.1f}, {snr_values.max():.1f}] dB")

def create_plots(df):
    """Create visualization plots"""
    print("\n=== CREATING PLOTS ===")
    
    # Set up the plotting style
    plt.style.use('default')
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('LoRaWAN P2P Messaging System Performance Analysis', fontsize=16)
    
    # Plot 1: End-to-end delays
    ack_with_delays = df[(df['message_type'] == 'ACK') & (df['end_to_end_delay_ms'].notna())]
    if len(ack_with_delays) > 0:
        delays = ack_with_delays['end_to_end_delay_ms'].astype(float) / 1000
        axes[0,0].hist(delays, bins=10, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0,0].set_xlabel('End-to-End Delay (seconds)')
        axes[0,0].set_ylabel('Frequency')
        axes[0,0].set_title('Distribution of End-to-End Delays')
        axes[0,0].grid(True, alpha=0.3)
    
    # Plot 2: Success rates by message type
    message_counts = df['message_type'].value_counts()
    axes[0,1].bar(message_counts.index, message_counts.values, color=['lightcoral', 'lightgreen', 'gold', 'lightblue'])
    axes[0,1].set_xlabel('Message Type')
    axes[0,1].set_ylabel('Count')
    axes[0,1].set_title('Message Type Distribution')
    axes[0,1].tick_params(axis='x', rotation=45)
    
    # Plot 3: RSSI distribution
    numeric_rssi = pd.to_numeric(df['rssi'], errors='coerce').dropna()
    if len(numeric_rssi) > 0:
        axes[1,0].hist(numeric_rssi, bins=15, alpha=0.7, color='orange', edgecolor='black')
        axes[1,0].set_xlabel('RSSI (dBm)')
        axes[1,0].set_ylabel('Frequency')
        axes[1,0].set_title('RSSI Distribution')
        axes[1,0].grid(True, alpha=0.3)
    
    # Plot 4: Delay vs Spreading Factor (if available)
    if 'spreading_factor' in ack_with_delays.columns and len(ack_with_delays) > 0:
        sf_delays = []
        sf_labels = []
        for sf in ack_with_delays['spreading_factor'].unique():
            if sf and str(sf) != 'nan':
                sf_delay_data = delays[ack_with_delays['spreading_factor'] == sf]
                if len(sf_delay_data) > 0:
                    sf_delays.append(sf_delay_data.values)
                    sf_labels.append(sf)
        
        if sf_delays:
            axes[1,1].boxplot(sf_delays, labels=sf_labels)
            axes[1,1].set_xlabel('Spreading Factor')
            axes[1,1].set_ylabel('End-to-End Delay (seconds)')
            axes[1,1].set_title('Delay vs Spreading Factor')
            axes[1,1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/performance_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print("Plots saved to: plots/performance_analysis.png")

def calculate_energy_estimates():
    """Calculate energy consumption estimates using typical LoRaWAN values"""
    print("\n=== ENERGY CONSUMPTION ESTIMATES ===")
    print("(Based on typical LoRaWAN device power consumption)")
    
    # Typical power consumption values for LoRaWAN
    tx_power = {
        'SF7': 45,   # mA during transmission
        'SF9': 48,   # mA during transmission  
        'SF12': 52   # mA during transmission
    }
    
    tx_time = {
        'SF7': 0.1,   # seconds for typical payload
        'SF9': 0.2,   # seconds for typical payload
        'SF12': 1.0   # seconds for typical payload
    }
    
    sleep_power = 0.01  # mA during sleep
    rx_power = 12       # mA during receive
    
    polling_intervals = [60, 120, 180]  # seconds
    
    print("Estimated battery life for different configurations:")
    print("(Assuming 2000mAh battery)")
    
    for interval in polling_intervals:
        print(f"\nPolling interval: {interval}s")
        for sf in ['SF7', 'SF9', 'SF12']:
            # Calculate average current consumption
            tx_current = tx_power[sf] * tx_time[sf] / interval
            sleep_current = sleep_power * (interval - tx_time[sf] - 0.1) / interval
            rx_current = rx_power * 0.1 / interval  # Assume 0.1s receive window
            
            total_current = tx_current + sleep_current + rx_current
            battery_life_hours = 2000 / total_current
            battery_life_days = battery_life_hours / 24
            
            print(f"  {sf}: {total_current:.2f}mA avg → {battery_life_days:.0f} days")

def main():
    """Main analysis function"""
    print("LoRaWAN P2P Messaging System - Experimental Analysis")
    print("=" * 55)
    
    # Load data
    try:
        df = load_data('data/SF9_120.csv')
        print(f"Loaded {len(df)} log entries")
    except FileNotFoundError:
        print("Error: experimental_log.csv not found in data/ directory")
        return
    
    # Create plots directory
    import os
    os.makedirs('plots', exist_ok=True)
    
    # Run all analyses
    analyze_roster_accuracy(df)
    analyze_delivery_success(df)
    delays = analyze_end_to_end_delays(df)
    analyze_rssi_snr(df)
    
    # Create visualizations
    create_plots(df)
    
    # Energy analysis
    calculate_energy_estimates()
    
    print("\n" + "=" * 55)
    print("Analysis complete! Check plots/ directory for visualizations.")
    print("Use this data for your report's Results and Discussion sections.")

if __name__ == "__main__":
    main()