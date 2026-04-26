"""
run_live_demo.py

Continuously runs agents against the remote backend server to feed live data 
to the Next.js frontend dashboard.
"""
import argparse
import time
import subprocess
import os

def run_loop(agent: str, delay: float, task: str):
    print(f"[*] Starting continuous live simulation feeder (Agent: {agent}, Task: {task})")
    print(f"[*] Delay between episodes: {delay}s")
    print("[*] Press Ctrl+C to stop.")
    
    episode_count = 1
    while True:
        try:
            print(f"\n--- Starting Episode {episode_count} ---")
            # We run `inference.py` which handles connecting via REST API 
            # to the backend server and running a single episode (or more)
            cmd = [
                "python", 
                "inference.py", 
                "--agent", agent, 
                "--task", task,
                "--episodes", "1", 
                "--remote", 
                "--server-url", "http://localhost:8000"
            ]
            
            # Since inference scripts can finish 50 steps very rapidly, 
            # the visual dashboard might only catch 1 or 2 polls. 
            # If the user wants a truly "slowed down" visualization per step, 
            # we'd normally throttle the agent's inner loop. But this script at least 
            # keeps the server populated with fresh trajectory data constantly.
            process = subprocess.run(cmd, check=True)
            
            time.sleep(delay)
            episode_count += 1

        except subprocess.CalledProcessError as e:
            print(f"[!] Target backend server might not be running or reachable. Retrying in 5s... (Error: {e})")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[*] Live simulation feeder stopped by user.")
            break
        except Exception as e:
            print(f"[!] Unexpected error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Dashboard Feed Simulator")
    parser.add_argument("--agent", type=str, default="hybrid", help="Agent type (baseline, llm, hybrid)")
    parser.add_argument("--task", type=str, default="task3", help="Task difficulty (task1, task2, task3)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between episodes in seconds")
    
    args = parser.parse_args()
    
    # Check if we are in the right directory
    if not os.path.exists("inference.py"):
        print("[!] Warning: inference.py not found in current directory. Please run from FeatureFlag root.")
        exit(1)

    run_loop(args.agent, args.delay, args.task)
