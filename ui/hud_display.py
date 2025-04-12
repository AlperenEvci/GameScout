# gamescout/ui/hud_display.py

import tkinter as tk
from tkinter import ttk # Themed Tkinter widgets
from config import settings
from utils.helpers import get_logger
import threading
import queue # For thread-safe communication

logger = get_logger(__name__)

class HudWindow(threading.Thread):
    """
    Manages the HUD display window in a separate thread using Tkinter.
    """
    def __init__(self, update_queue: queue.Queue):
        super().__init__(daemon=True) # Daemon thread exits when main program exits
        self.update_queue = update_queue
        self.root = None
        self.info_label = None
        self._stop_event = threading.Event()

    def stop(self):
        """Signals the thread to stop."""
        self._stop_event.set()
        if self.root:
            # Schedule the destroy action to run in the Tkinter main loop
            self.root.after(0, self.root.destroy)
        logger.info("HUD stop requested.")

    def run(self):
        """The main loop for the Tkinter window."""
        logger.info("HUD thread starting.")
        try:
            self.root = tk.Tk()
            self.root.title(f"{settings.APP_NAME} HUD")
            self.root.geometry(f"{settings.HUD_WIDTH}x{settings.HUD_HEIGHT}")

            # Make window stay on top
            self.root.wm_attributes("-topmost", 1)
            # Make window (partially) transparent (may depend on OS/window manager)
            try:
                self.root.attributes("-alpha", settings.HUD_TRANSPARENCY)
            except tk.TclError:
                logger.warning("Window transparency (-alpha) not supported on this system.")

            # Add a distinctive border to make HUD more visible
            self.root.configure(bg="green")  # Bright color for the border
            
            # --- Add HUD elements ---
            style = ttk.Style()
            style.configure("TLabel", background="black", foreground="#00FF00", padding=5, font=('Helvetica', 10, 'bold'))  # Brighter text
            style.configure("TFrame", background="black")

            main_frame = ttk.Frame(self.root, padding="5", style="TFrame")
            main_frame.pack(expand=True, fill=tk.BOTH)

            self.info_label = ttk.Label(
                main_frame,
                text="Initializing GameScout HUD...",
                wraplength=settings.HUD_WIDTH - 20, # Wrap text within window width
                justify=tk.LEFT,
                style="TLabel"
            )
            self.info_label.pack(pady=5, padx=5, anchor='nw')

            # Schedule the first check for updates
            self.root.after(settings.HUD_UPDATE_INTERVAL_MS, self.check_queue)

            logger.info("HUD window created. Starting main loop.")
            self.root.mainloop()

        except Exception as e:
            logger.error(f"Error in HUD thread: {e}", exc_info=True)
        finally:
            logger.info("HUD thread finished.")
            self.root = None # Ensure root is cleared if loop exits

    def check_queue(self):
        """Checks the queue for new text and updates the label."""
        if self._stop_event.is_set():
            logger.debug("Stop event set, skipping queue check.")
            return # Don't reschedule if stopping

        try:
            # Process all available messages in the queue non-blockingly
            while True:
                try:
                    new_text = self.update_queue.get_nowait()
                    if self.info_label and self.root: # Check if widgets still exist
                        self.info_label.config(text=new_text)
                        logger.debug(f"HUD updated with new text: {new_text[:50]}...")
                    self.update_queue.task_done()
                except queue.Empty:
                    break # No more messages
                except tk.TclError as e:
                     # Handle cases where the widget might be destroyed during update
                     logger.warning(f"Tkinter error during HUD update (widget likely destroyed): {e}")
                     break # Stop trying to update if widget is gone
                except Exception as e:
                    logger.error(f"Error processing HUD update queue: {e}", exc_info=True)
                    break # Avoid potential infinite loop on unexpected errors


        except Exception as e:
            logger.error(f"Error in check_queue: {e}", exc_info=True)

        # Reschedule the check only if not stopping and root exists
        if not self._stop_event.is_set() and self.root:
            self.root.after(settings.HUD_UPDATE_INTERVAL_MS, self.check_queue)


if __name__ == '__main__':
    # Example usage: Start the HUD and send updates
    print("Testing HUD Display...")
    q = queue.Queue()
    hud = HudWindow(q)
    hud.start()
    print("HUD thread started. Sending test messages...")

    try:
        # Send some test messages
        q.put("Test Message 1: Welcome!")
        import time
        time.sleep(2)
        q.put("Test Message 2: This is a longer message that should wrap around nicely within the HUD window bounds.")
        time.sleep(2)
        q.put("Test Message 3: Updating again...")
        time.sleep(5) # Keep running for a bit

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received.")
    finally:
        print("Stopping HUD...")
        hud.stop()
        hud.join(timeout=2) # Wait for the thread to finish
        print("HUD test finished.")
