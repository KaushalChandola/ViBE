import sys
import threading
import cv2
import pyttsx3
import speech_recognition as sr
from queue import Queue, Empty
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLabel, QPushButton, QTextEdit, QGroupBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon

# Initialize text-to-speech engine
engine = pyttsx3.init()


def speak_with_style(text):
    """Convert text to speech"""
    engine.say(text)
    engine.runAndWait()


def speech_to_text_with_indicator():
    """Convert speech to text"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.adjust_for_ambient_noise(source)
        audio = r.listen(source)

    try:
        text = r.recognize_google(audio)
        print(f"Recognized: {text}")
        return text
    except sr.UnknownValueError:
        print("Could not understand audio")
        return None
    except sr.RequestError as e:
        print(f"Could not request results; {e}")
        return None


class VisualAssistantUI(QMainWindow):
    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant
        self.setup_ui()
        self.setup_accessibility()

    def setup_ui(self):
        """Set up the main user interface"""
        self.setWindowTitle("Visual Assistant for Visually Impaired")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon('assistant_icon.png'))  # Add your icon file

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Status display
        self.status_group = QGroupBox("System Status")
        self.status_layout = QVBoxLayout()
        self.status_label = QLabel("Assistant ready")
        self.status_label.setWordWrap(True)
        self.status_layout.addWidget(self.status_label)
        self.status_group.setLayout(self.status_layout)
        layout.addWidget(self.status_group)

        # Command interface
        self.command_group = QGroupBox("Voice Commands")
        command_layout = QVBoxLayout()

        self.command_button = QPushButton("Speak Command (Spacebar)")
        self.command_button.clicked.connect(self.start_listening)
        command_layout.addWidget(self.command_button)

        self.last_command_label = QLabel("Last command: None")
        command_layout.addWidget(self.last_command_label)

        self.command_group.setLayout(command_layout)
        layout.addWidget(self.command_group)

        # Object detection display
        self.detection_group = QGroupBox("Object Detection")
        detection_layout = QVBoxLayout()

        self.detection_label = QLabel("No objects detected yet")
        self.detection_label.setWordWrap(True)
        detection_layout.addWidget(self.detection_label)

        self.detect_button = QPushButton("Describe Scene (D)")
        self.detect_button.clicked.connect(self.assistant.describe_scene)
        detection_layout.addWidget(self.detect_button)

        self.detection_group.setLayout(detection_layout)
        layout.addWidget(self.detection_group)

        # System log
        self.log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout()

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)

        self.log_group.setLayout(log_layout)
        layout.addWidget(self.log_group)

        # Shortcuts
        self.command_button.setShortcut(Qt.Key_Space)
        self.detect_button.setShortcut(Qt.Key_D)

        # Timer for updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_ui)
        self.update_timer.start(500)  # Update twice per second

    def setup_accessibility(self):
        """Configure accessibility features"""
        # High contrast mode
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: #FFFFFF;
            }
            QGroupBox {
                font-size: 16px;
                border: 2px solid #FFFFFF;
                margin-top: 10px;
            }
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                padding: 10px;
                font-size: 16px;
                min-width: 200px;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
            QTextEdit {
                background-color: #111111;
                color: #FFFFFF;
                font-family: monospace;
            }
        """)

        # Large fonts
        big_font = QFont()
        big_font.setPointSize(14)
        self.setFont(big_font)

        # Screen reader support
        self.setAttribute(Qt.WA_AlwaysShowToolTips, True)
        self.status_label.setToolTip("Current system status")
        self.command_button.setToolTip("Press to speak a command or press spacebar")
        self.detect_button.setToolTip("Press to describe the current scene or press D")

    def update_ui(self):
        """Update UI elements periodically"""
        # Update status from assistant
        if not self.assistant.running:
            self.status_label.setText("Assistant shutting down...")

        # Update last command
        if hasattr(self.assistant, 'last_command'):
            self.last_command_label.setText(f"Last command: {self.assistant.last_command}")

        # Update detection results
        if hasattr(self.assistant, 'last_detection'):
            self.detection_label.setText(
                "Detected objects:\n" + "\n".join(f"- {obj}" for obj in self.assistant.last_detection))

    def start_listening(self):
        """Handle the listen command button"""
        self.status_label.setText("Listening...")
        self.command_button.setEnabled(False)

        # Run speech recognition in a separate thread
        threading.Thread(target=self.run_speech_recognition, daemon=True).start()

    def run_speech_recognition(self):
        """Run speech recognition and update UI when done"""
        command = speech_to_text_with_indicator()
        if command:
            self.log_message(f"User command: {command}")
            self.assistant.command_queue.put(command.lower())

        self.command_button.setEnabled(True)
        self.status_label.setText("Ready for next command")

    def log_message(self, message):
        """Add a message to the log display"""
        self.log_display.append(message)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        """Handle window close event"""
        self.assistant.stop()
        event.accept()


class VisualAssistant:
    def __init__(self):
        self.command_queue = Queue()
        self.running = True
        self.last_command = None
        self.last_detection = []
        self.camera = cv2.VideoCapture(0)

        if not self.camera.isOpened():
            self.log_message("Warning: Camera not detected. Some features may not work.")

        self.commands = {
            "what do you see": self.describe_scene,
            "what's in front of me": self.describe_scene,
            "describe the scene": self.describe_scene,
            "help": self.help_command,
            "stop": self.stop,
            "exit": self.stop,
            "hello": lambda: self.speak("Hello! How can I assist you today?"),
            "thank you": lambda: self.speak("You're welcome!"),
        }

    def describe_scene(self):
        """Describe the current scene using object detection"""
        ret, frame = self.camera.read()
        if ret:
            # Add your actual object detection code here
            detected_objects = ["chair", "table", "person"]  # Example detection
            self.last_detection = detected_objects
            description = "I see " + ", ".join(detected_objects)
            self.speak(description)
        else:
            self.speak("I can't see anything right now.")

    def speak(self, text):
        """Wrapper for speak_with_style that also updates UI"""
        speak_with_style(text)
        if hasattr(self, 'ui'):
            self.ui.log_message(f"Assistant: {text}")

    def log_message(self, message):
        """Log a message to the UI if available"""
        if hasattr(self, 'ui'):
            self.ui.log_message(message)

    def help_command(self):
        """Provide help information"""
        help_text = "Available commands: " + ", ".join(self.commands.keys())
        self.speak(help_text)

    def stop(self):
        """Stop the assistant"""
        self.running = False
        self.camera.release()
        self.speak("Goodbye!")

    def start(self):
        """Main processing loop"""
        self.speak("Visual assistant started. How can I help you?")
        while self.running:
            try:
                command = self.command_queue.get(timeout=0.1)
                self.last_command = command

                if command in self.commands:
                    self.commands[command]()
                else:
                    self.speak(f"I don't understand the command: {command}")

            except Empty:
                continue


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    try:
        assistant = VisualAssistant()
        ui = VisualAssistantUI(assistant)
        assistant.ui = ui  # Connect UI to assistant

        ui.show()

        # Start assistant in separate thread
        assistant_thread = threading.Thread(target=assistant.start, daemon=True)
        assistant_thread.start()

        sys.exit(app.exec_())
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)