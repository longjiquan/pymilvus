import datetime

from .types import DataType
from .constants import LOGICAL_BITS, LOGICAL_BITS_MASK
from ..exceptions import ParamError, MilvusException

valid_index_types = [
    "GPU_FLAT",
    "GPU_IVF_FLAT",
    "GPU_IVF_SQ8",
    "GPU_IVF_PQ",
    "RAFT_IVF_FLAT",
    "RAFT_IVF_PQ",
    "FLAT",
    "IVF_FLAT",
    "IVF_SQ8",
    "IVF_PQ",
    "HNSW",
    "ANNOY",
    "BIN_FLAT",
    "BIN_IVF_FLAT",
    "DISKANN",
    "AUTOINDEX"
]

valid_index_params_keys = [
    "nlist",
    "m",
    "nbits",
    "M",
    "efConstruction",
    "PQM",
    "n_trees"
]

valid_binary_index_types = [
    "BIN_FLAT",
    "BIN_IVF_FLAT"
]

valid_binary_metric_types = [
    "JACCARD",
    "HAMMING",
    "TANIMOTO",
    "SUBSTRUCTURE",
    "SUPERSTRUCTURE"
]


def hybridts_to_unixtime(ts):
    physical = ts >> LOGICAL_BITS
    return physical / 1000.0


def mkts_from_hybridts(hybridts, milliseconds=0., delta=None):
    if not isinstance(milliseconds, (int, float)):
        raise MilvusException(message="parameter milliseconds should be type of int or float")

    if isinstance(delta, datetime.timedelta):
        milliseconds += (delta.microseconds / 1000.0)
    elif delta is not None:
        raise MilvusException(message="parameter delta should be type of datetime.timedelta")

    if not isinstance(hybridts, int):
        raise MilvusException(message="parameter hybridts should be type of int")

    logical = hybridts & LOGICAL_BITS_MASK
    physical = hybridts >> LOGICAL_BITS

    new_ts = int((int((physical + milliseconds)) << LOGICAL_BITS) + logical)
    return new_ts


def mkts_from_unixtime(epoch, milliseconds=0., delta=None):
    if not isinstance(epoch, (int, float)):
        raise MilvusException(message="parameter epoch should be type of int or float")

    if not isinstance(milliseconds, (int, float)):
        raise MilvusException(message="parameter milliseconds should be type of int or float")

    if isinstance(delta, datetime.timedelta):
        milliseconds += (delta.microseconds / 1000.0)
    elif delta is not None:
        raise MilvusException(message="parameter delta should be type of datetime.timedelta")

    epoch += (milliseconds / 1000.0)
    int_msecs = int(epoch * 1000 // 1)
    return int(int_msecs << LOGICAL_BITS)


def mkts_from_datetime(d_time, milliseconds=0., delta=None):
    if not isinstance(d_time, datetime.datetime):
        raise MilvusException(message="parameter d_time should be type of datetime.datetime")

    return mkts_from_unixtime(d_time.timestamp(), milliseconds=milliseconds, delta=delta)


def check_invalid_binary_vector(entities) -> bool:
    for entity in entities:
        if entity['type'] == DataType.BINARY_VECTOR:
            if not isinstance(entity['values'], list) and len(entity['values']) == 0:
                return False

            dim = len(entity['values'][0]) * 8
            if dim == 0:
                return False

            for values in entity['values']:
                if len(values) * 8 != dim:
                    return False
                if not isinstance(values, bytes):
                    return False
    return True


def len_of(field_data) -> int:
    if field_data.HasField("scalars"):
        if field_data.scalars.HasField("bool_data"):
            return len(field_data.scalars.bool_data.data)

        if field_data.scalars.HasField("int_data"):
            return len(field_data.scalars.int_data.data)

        if field_data.scalars.HasField("long_data"):
            return len(field_data.scalars.long_data.data)

        if field_data.scalars.HasField("float_data"):
            return len(field_data.scalars.float_data.data)

        if field_data.scalars.HasField("double_data"):
            return len(field_data.scalars.double_data.data)

        if field_data.scalars.HasField("string_data"):
            return len(field_data.scalars.string_data.data)

        if field_data.scalars.HasField("bytes_data"):
            return len(field_data.scalars.bytes_data.data)

        raise MilvusException(message="Unsupported scalar type")

    if field_data.HasField("vectors"):
        dim = field_data.vectors.dim
        if field_data.vectors.HasField("float_vector"):
            total_len = len(field_data.vectors.float_vector.data)
            if total_len % dim != 0:
                raise MilvusException(message=f"Invalid vector length: total_len={total_len}, dim={dim}")
            return int(total_len / dim)

        total_len = len(field_data.vectors.binary_vector)
        return int(total_len / (dim / 8))

    raise MilvusException(message="Unknown data type")


def traverse_info(fields_info, entities):
    location, primary_key_loc, auto_id_loc = {}, None, None
    for i, field in enumerate(fields_info):
        if field.get("is_primary", False):
            primary_key_loc = i

        if field.get("auto_id", False):
            auto_id_loc = i
            continue

        match_flag = False
        field_name = field["name"]
        field_type = field["type"]

        for entity in entities:
            entity_name, entity_type = entity["name"], entity["type"]

            if field_name == entity_name:
                if field_type != entity_type:
                    raise ParamError(message=f"Collection field type is {field_type}"
                                     f", but entities field type is {entity_type}")

                entity_dim, field_dim = 0, 0
                if entity_type in [DataType.FLOAT_VECTOR, DataType.BINARY_VECTOR]:
                    field_dim = field["params"]["dim"]
                    entity_dim = len(entity["values"][0])

                if entity_type in [DataType.FLOAT_VECTOR, ] and entity_dim != field_dim:
                    raise ParamError(message=f"Collection field dim is {field_dim}"
                                     f", but entities field dim is {entity_dim}")

                if entity_type in [DataType.BINARY_VECTOR, ] and entity_dim * 8 != field_dim:
                    raise ParamError(message=f"Collection field dim is {field_dim}"
                                     f", but entities field dim is {entity_dim * 8}")

                location[field["name"]] = i
                match_flag = True
                break

        if not match_flag:
            raise ParamError(
                message=f"Field {field['name']} don't match in entities")

    return location, primary_key_loc, auto_id_loc
