import os
from concurrent import futures

import boto3
import db_service.db_handler_pb2 as db_pb2
import db_service.db_handler_pb2_grpc as db_pb2_grpc
import grpc
import storage.storage_service_pb2 as storage_pb2
import storage.storage_service_pb2_grpc as storage_pb2_grpc
from dotenv import load_dotenv
from PIL import Image

load_dotenv()
db_service_channel = grpc.insecure_channel(
    f"{os.getenv('DB_SERVICE_HOST')}:{os.getenv('DB_SERVICE_PORT')}"
)
db_service_stub = db_pb2_grpc.DBServiceStub(db_service_channel)


class StorageService(storage_pb2_grpc.StorageServiceServicer):
    def Put(self, request, context):
        print(request)
        filename = None
        uuid = None
        for chunk in request:
            filename = chunk.filename
            uuid = chunk.uuid
            with open(filename, "ab") as f:
                f.write(chunk.data)
        filename_webp = filename.split(".")[0] + ".webp"
        if ".webp" in filename:
            filename_webp = filename
        else:
            with Image.open(filename) as im:
                im.save(filename_webp, format="webp")
            os.remove(filename)
        session = boto3.session.Session()
        s3 = session.client(
            service_name='s3',
            endpoint_url='https://storage.yandexcloud.net',
        )
        s3.upload_file(f"./{filename_webp}", "capyavatars", f"avatar/{uuid}/{filename_webp}")
        os.remove(filename_webp)
        db_request = db_pb2.SetAvatarRequest(
            uuid=uuid,
            avatar=filename_webp
        )
        db_response = db_service_stub.set_avatar(db_request)
        return storage_pb2.PutResponse(status=db_response.status, description=db_response.description)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    storage_pb2_grpc.add_StorageServiceServicer_to_server(
        StorageService(), server)
    server.add_insecure_port(f'[::]:{os.getenv("GRPC_PORT")}')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
