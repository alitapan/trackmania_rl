# bridge.py
import logging
from flask import Flask, request
from threading import Lock
from shared.schemas import Telemetry
from waitress import serve
from threading import Lock, Thread

class TelemetryBridge:
    def __init__(self, host="127.0.0.1", port=5000, log_path="bridge.log"):
        """
        Initializes the TelemetryBridge instance.

        This method initializes a Flask app and sets up logging to a file.

        Parameters
        ----------
        host : str, optional
            The host to run the TelemetryBridge on. Defaults to "127.0.0.1".
        port : int, optional
            The port to run the TelemetryBridge on. Defaults to 5000.
        log_path : str, optional
            The path to the log file. Defaults to "bridge.log".
        """

        self.app = Flask(__name__)

        self.latest_telemetry = None
        self.telemetry_lock = Lock()

        self.host = host
        self.port = port
        self.log_path = log_path
        self.server_thread = None

        # Set up logging
        self.logger = logging.getLogger(f"TelemetryBridge:{self.port}")
        self.logger.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler = logging.FileHandler(self.log_path)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self.logger.propagate = False
        self._setup_routes()


    def _setup_routes(self):
        """
        Set up the Flask routes for the TelemetryBridge application.

        Defines the /telemetry route which accepts POST requests with telemetry 
        data. The received data is parsed into a Telemetry object and stored as 
        the latest telemetry data. Logs the telemetry data for debugging purposes.
        In case of errors during parsing, logs the error and returns an error 
        response.
        """
        @self.app.route("/telemetry", methods=["POST"])
        def receive_telemetry():
            try:
                data = request.get_json()
                telemetry = Telemetry.from_dict(data)
                with self.telemetry_lock:
                    self.latest_telemetry = telemetry
                self.logger.debug(f"Telemetry: {telemetry}")
                return {"status": "ok"}, 200
            except Exception as e:
                self.logger.error("Failed to parse telemetry:", exc_info=True)
                return {"error": str(e)}, 400

    def get_latest_telemetry(self) -> Telemetry:
        """
        Retrieve the latest telemetry data.

        Returns:
            Telemetry: The most recent telemetry data received, or None if no
            telemetry data has been received yet.
        """

        with self.telemetry_lock:
            return self.latest_telemetry
        
    def start(self):
        """
        Start the TelemetryBridge server in a separate thread.

        This method initializes and starts a background thread that runs the 
        TelemetryBridge server using the Waitress WSGI server. The server listens 
        for incoming telemetry data on the specified host and port. Logs the 
        server start information for debugging purposes.
        """

        def run():
            serve(self.app, host=self.host, port=self.port)

        self.server_thread = Thread(target=run, daemon=True)
        self.server_thread.start()
        self.logger.info(f"[TelemetryBridge] Started on http://{self.host}:{self.port}")

    @property
    def app_instance(self):
        return self.app