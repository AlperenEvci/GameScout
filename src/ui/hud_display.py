# gamescout/ui/hud_display.py
"""
HUD Display Module for GameScout

This module provides a Heads-Up Display (HUD) window that shows game information
and recommendations to the player in real-time. It runs in a separate thread
to avoid blocking the main application.
"""

import tkinter as tk
from tkinter import ttk, font  # Themed Tkinter widgets
from config import settings
from utils.helpers import get_logger
import threading
import queue  # For thread-safe communication

logger = get_logger(__name__)

class HudWindow(threading.Thread):
    """
    Manages the HUD display window using Tkinter in a separate thread.
    
    The HUD window shows game information, detected regions, and recommendations
    to the player while the game is running.
    """
    def __init__(self, update_queue: queue.Queue):
        super().__init__(daemon=True)  # Terminate thread when main program ends
        self.update_queue = update_queue
        self.root = None
        self.info_label = None
        self._stop_event = threading.Event()
        self.theme = "dark"  # default theme

    def stop(self):
        """Signals the thread to stop."""
        self._stop_event.set()
        if self.root:
            # Schedule destroy operation in Tkinter main loop
            self.root.after(0, self.root.destroy)
        logger.info("HUD stop request received.")

    def run(self):
        """Main loop for the Tkinter window."""
        logger.info("Starting HUD thread.")
        try:
            self.root = tk.Tk()
            self.root.title(f"{settings.APP_NAME} HUD")
            self.root.geometry(f"{settings.HUD_WIDTH}x{settings.HUD_HEIGHT}")

            # Keep window always on top
            self.root.wm_attributes("-topmost", 1)
            # Make window (partially) transparent (may depend on OS/window manager)
            try:
                self.root.attributes("-alpha", settings.HUD_TRANSPARENCY)
            except tk.TclError:
                logger.warning("Window transparency (-alpha) not supported on this system.")

            # --- Theme settings ---
            if self.theme == "dark":
                bg_color = "#1E1E1E"  # Dark background
                fg_color = "#00FF00"  # Green text
                highlight_color = "#3700B3"  # Highlight color
            else:  # light theme
                bg_color = "#F0F0F0"  # Light background
                fg_color = "#007700"  # Dark green text
                highlight_color = "#BB86FC"  # Highlight color

            # Add a distinct border to make HUD more visible
            self.root.configure(bg=highlight_color)  # Color for border
            
            # --- Add HUD elements ---
            style = ttk.Style()
            style.configure("TLabel", background=bg_color, foreground=fg_color, padding=5, font=('Helvetica', 10, 'bold'))
            style.configure("TFrame", background=bg_color)

            main_frame = ttk.Frame(self.root, padding="5", style="TFrame")
            main_frame.pack(expand=True, fill=tk.BOTH)

            # Title area
            header_frame = ttk.Frame(main_frame, style="TFrame")
            header_frame.pack(fill=tk.X, pady=(0, 5))
            
            title_font = font.Font(family="Helvetica", size=12, weight="bold")
            title_label = tk.Label(
                header_frame, 
                text=f"{settings.APP_NAME}", 
                font=title_font,
                background=bg_color,
                foreground=fg_color
            )
            title_label.pack(side=tk.LEFT)
            
            # Main content area
            self.info_label = ttk.Label(
                main_frame,
                text="Starting GameScout HUD...",
                wraplength=settings.HUD_WIDTH - 20,  # Wrap text to fit window width
                justify=tk.LEFT,
                style="TLabel"
            )
            self.info_label.pack(pady=5, padx=5, anchor='nw', fill=tk.BOTH, expand=True)

            # Schedule first update check
            self.root.after(settings.HUD_UPDATE_INTERVAL_MS, self.check_queue)

            # Add keyboard shortcuts
            self.root.bind("<Escape>", lambda e: self.toggle_visibility())
            self.root.bind("<F1>", lambda e: self.toggle_theme())

            logger.info("HUD window created. Starting main loop.")
            self.root.mainloop()

        except Exception as e:
            logger.error(f"Error in HUD thread: {e}", exc_info=True)
        finally:
            logger.info("HUD thread terminated.")
            self.root = None  # Ensure root is cleaned up after loop exit

    def toggle_visibility(self):
        """Toggle HUD window visibility (hide/show)."""
        if self.root:
            if self.root.winfo_viewable():
                self.root.withdraw()  # Hide window
                logger.debug("HUD hidden")
            else:
                self.root.deiconify()  # Show window
                self.root.lift()  # Bring window to front
                logger.debug("HUD shown")

    def toggle_theme(self):
        """Toggle between light and dark themes."""
        if self.theme == "dark":
            self.theme = "light"
        else:
            self.theme = "dark"
        
        # We would need to recreate the window for theme changes
        # For now, just log the change
        logger.info(f"Theme changed to: {self.theme}")
        
        # Ideally, we would update all widget colors here
        # But for this simple example, we're ignoring that

    def format_rag_response(self, text):
        """
        Format RAG responses for better readability.
        
        Detects and formats question/answer pairs in RAG responses
        to make them more visually distinct.
        
        Args:
            text: The text to format
            
        Returns:
            Formatted text
        """
        if "📝 Soru:" in text and "🔍 Yanıt:" in text:
            # Convert Turkish markers to English
            text = text.replace("📝 Soru:", "📝 Question:")
            text = text.replace("🔍 Yanıt:", "🔍 Answer:")
            
        if "📝 Question:" in text and "🔍 Answer:" in text:
            parts = text.split("🔍 Answer:")
            if len(parts) == 2:
                question_part = parts[0].replace("📝 Question:", "").strip()
                answer_part = parts[1].strip()
                
                formatted = f"📝 QUESTION: {question_part}\n\n"
                formatted += f"🔍 ANSWER: {answer_part}"
                return formatted
        
        return text  # Return original text if format doesn't match

    def check_queue(self):
        """
        Check queue for new text updates and update the label.
        
        This method polls the update queue for new messages and updates
        the HUD display accordingly. It reschedules itself to run
        periodically unless the thread is stopping.
        """
        if self._stop_event.is_set():
            logger.debug("Stop event set, skipping queue check.")
            return  # Don't reschedule if stopping

        try:
            # Process all current messages in queue without blocking
            while True:
                try:
                    new_text = self.update_queue.get_nowait()
                    if self.info_label and self.root:  # Check that widgets still exist
                        # Format RAG responses
                        formatted_text = self.format_rag_response(new_text)
                        self.info_label.config(text=formatted_text)
                        logger.debug(f"HUD updated with new text: {new_text[:50]}...")
                    self.update_queue.task_done()
                except queue.Empty:
                    break  # No more messages
                except tk.TclError as e:
                     # Handle cases where widget might be destroyed during update
                     logger.warning(f"Tkinter error during HUD update (widget likely destroyed): {e}")
                     break  # Don't continue trying to update if widget gone
                except Exception as e:
                    logger.error(f"Error processing HUD update queue: {e}", exc_info=True)
                    break  # Avoid potential infinite loop on unexpected errors

        except Exception as e:
            logger.error(f"Error in check_queue: {e}", exc_info=True)

        # Reschedule check if not stopping and root exists
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
        q.put("Test Message 2: This is a longer message that should wrap nicely within the HUD window bounds.")
        time.sleep(2)
        q.put("Test Message 3: Updating again...")
        time.sleep(2)
        
        # Test message in RAG format
        rag_test = """
📝 Question: Who is Shadowheart?

🔍 Answer: 
Shadowheart is a Half-Elf who is a Cleric of Shar and the main cleric character in the party. 
She has a secretive background and connections with the cult that worships the Absolute. 
She has a dark and mysterious personality, but can develop loyalty to your character over time.
        """
        q.put(rag_test)
        time.sleep(5)  # Keep running for a while

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received.")
    finally:
        print("Stopping HUD...")
        hud.stop()
        hud.join(timeout=2)  # Wait for thread to finish
        print("HUD test completed.")
