import json

from spindrift.network import Handler, Network


class Context:

    def __init__(self):
        self.jobs = {}
        self.deleted = []
        self.waiting = []
        self.max_id = 0

    @property
    def next_id(self):
        self.max_id += 1
        return self.max_id

    def is_valid(self, id):
        return id <= self.max_id and id not in self.deleted

    def add_job(self, id, job):

        def check_waiting():
            for i in range(len(self.waiting) - 1, -1, -1):
                connection, queues = self.waiting[i]
                if connection.is_closed:
                    del self.waiting[i]
                elif job["queue"] in queues:
                    del self.waiting[i]
                    connection.on_get_job(job)
                    connection.unquiesce()
                    return True
            return False

        if id not in self.deleted:
            if not check_waiting():
                self.jobs[id] = job

    def get_job(self, queues):
        match = sorted([(val["pri"], key, val)  # key resolves priority ties
                        for key, val in self.jobs.items()
                        if val["queue"] in queues])
        if match:
            _, id, job = match[-1]
            del self.jobs[id]
        else:
            job = None
        return job

    def wait_for_job(self, connection, queues):
        connection.quiesce()
        self.waiting.insert(0, [connection, queues])


class Connection(Handler):

    def on_init(self):
        self.buffer = ""
        self.working = {}

    def on_ready(self):
        print(f"{self.id=} open")

    def on_data(self, data):
        self.buffer += data.decode()
        while not self.is_quiesced and self.buffer.find("\n") != -1:
            message, self.buffer = self.buffer.split("\n", 1)
            self.on_message(message)

    def unquiesce(self):
        super().unquiesce()
        self.on_data(b"")  # handle buffered messages

    def on_close(self, reason):
        print(f"{self.id=} {self.rx_count=} close: {reason}")
        for key, val in self.working.items():
            self.context.add_job(key, val)

    # ---

    def respond(self, status, **kwargs):
        message = {"status": status, **kwargs}
        message = json.dumps(message) + "\n"
        self.send(message.encode())

    def on_get_job(self, job):
        if job:
            self.working[job["id"]] = job
            self.respond("ok", **job)
        else:
            self.respond("no-job")

    def on_message(self, message):
        try:
            command = json.loads(message)
        except Exception:
            self.respond("error", error="invalid command structure")
            return
        context = self.context

        print(f"{self.id=} {command=}")

        if (request := command.get("request")) == "get":
            queues = command["queues"]
            job = context.get_job(queues)
            if not job and command.get("wait", False):
                context.wait_for_job(self, queues)
            else:
                self.on_get_job(job)

        elif request == "put":
            queue = command["queue"]
            job = command["job"]
            pri = int(command["pri"])
            id = context.next_id
            job = dict(queue=queue, job=job, pri=pri, id=id)
            context.add_job(id, job)
            self.respond("ok", id=id)

        elif request == "abort":
            id = command["id"]
            if not context.is_valid(id):
                self.respond("no-job")
            elif id not in self.working:
                self.respond(
                    "error", error=f"job {id} not pending for this client")
            else:
                job = self.working.pop(id)
                context.add_job(id, job)
                self.respond("ok")

        elif request == "delete":
            id = command["id"]
            if not context.is_valid(id):
                self.respond("no-job")
            else:
                if id in context.jobs:
                    del context.jobs[id]
                context.deleted.append(id)
                self.respond("ok")

        else:
            self.respond("error", error=f"invalid request type {request}")


listener = Network()
listener.add_server(12345, Connection, Context())
while True:
    listener.service()
