import pytest
import time
import docker
from tests.common import rand_string
from sqlalchemy import create_engine
from snowshu.core.replica.replica_manager import ReplicaManager
from snowshu.core.docker import SnowShuDocker
from snowshu.adapters.target_adapters import PostgresAdapter

from snowshu.logger import Logger
Logger().set_log_level(0)

TEST_NAME, TEST_TABLE = [rand_string(10) for _ in range(2)]


@pytest.fixture
def kill_docker(autouse=True):
    shdocker = SnowShuDocker()
    shdocker.remove_container('snowshu_target')
    shdocker.remove_container(TEST_NAME)
    yield
    shdocker.remove_container('snowshu_target')
    shdocker.remove_container(TEST_NAME)


def test_creates_replica():
    # build image
    # load it up with some data
    # convert it to a replica
    # spin it all down
    # start the replica
    # query it and confirm that the data is in there

    shdocker = SnowShuDocker()
    target_adapter = PostgresAdapter()
    target_container = shdocker.startup(
        target_adapter.DOCKER_IMAGE,
        target_adapter.DOCKER_START_COMMAND,
        9999,
        target_adapter.CLASSNAME,

        ['POSTGRES_USER=snowshu',
         'POSTGRES_PASSWORD=snowshu',
         'POSTGRES_DB=snowshu', ])

    # load test data
    time.sleep(5)  # give pg a moment to spin up all the way
    engine = create_engine(
        'postgresql://snowshu:snowshu@snowshu_target:9999/snowshu')
    engine.execute(
        f'CREATE TABLE {TEST_TABLE} (column_one VARCHAR, column_two INT)')
    engine.execute(
        f"INSERT INTO {TEST_TABLE} VALUES ('a',1), ('b',2), ('c',3)")

    checkpoint = engine.execute(f"SELECT * FROM {TEST_TABLE}").fetchall()
    assert ('a', 1) == checkpoint[0]

    replica = shdocker.convert_container_to_replica(TEST_NAME,
                                                    target_container,
                                                    target_adapter)

    # get a new replica
    test_replica = ReplicaManager().get_replica(TEST_NAME, 9999)
    test_replica.launch()
    time.sleep(5)  # give pg a moment to spin up all the way
    engine = create_engine(
        f'postgresql://snowshu:snowshu@{test_replica.name}:9999/snowshu')
    res = engine.execute(f'SELECT * FROM {TEST_TABLE}').fetchall()
    assert ('a', 1,) in res
    assert ('b', 2,) in res
    assert ('c', 3,) in res
    shdocker.remove_container(TEST_NAME)
