from ..template import Knob


class MySQLKnobs(object):
    def __init__(self, max_memory_size):
        # Obtained from MySQL 8.0 documentation
        # TODO: fetch default value from mysql
        self.knobs_attrs = [
            {
                "name": 'table_open_cache',
                "range": [1, 524288],
                "default": 4000,
                "type": "int"
            },
            {
                "name": 'innodb_buffer_pool_size',
                "range": [5242880, max_memory_size], # maximum 2**64-1
                "default": 134217728, # Bytes = 128MB
                "type": "int"
            },
            {
                "name": 'innodb_buffer_pool_instances',
                "range": [1, 64],
                "default": 1, # 8 or (1 if innodb_buffer_pool_size < 1GB)
                "type": "int"
            },
            {
                "name": 'innodb_purge_threads',
                "range": [1, 32],
                "default": 4,
                "type": "int"
            },
            {
                "name": 'innodb_read_io_threads',
                "range": [1, 64],
                "default": 4,
                "type": "int"
            },
            {
                "name": 'innodb_write_io_threads',
                "range": [1, 64],
                "default": 4,
                "type": "int"
            },
        ]
        self.names = list(map(lambda x: x["name"], self.knobs_attrs))
        self.knobs = dict()

        # create dict of knobs for mysql
        for i, name in enumerate(self.names):
            self.knobs[name] = Knob(self.knobs_attrs[i])

    @property
    def num_knobs(self):
        return len(self.names)

    def __getitem__(self, key):
        return self.knobs[key].value

    def apply_action(self, action):
        for i, name in enumerate(self.names):
            self.knobs[name].apply_action(action[i])

    def save(self, metrics, knob_file):
        knob_strs = []
        for name in self.knobs.names:
            knob_strs.append('{}:{}'.format(name, self.knobs[name]))
        result_str = '{},{},{},'.format(metrics[0], metrics[1], metrics[2])
        knob_str = "#".join(knob_strs)
        result_str += knob_str

        with open(knob_file, 'a+') as f:
            f.write(result_str+'\n')


if __name__ == "__main__":
    from pprint import pprint
    import numpy as np

    max_memory_size = 4 * 1024 * 1024 * 1024
    mysql_knobs = MySQLKnobs(max_memory_size)
    print(mysql_knobs.num_knobs)
    print(mysql_knobs)
    pprint(mysql_knobs.knobs)

    # generate random action
    for i in range(10):
        action = np.random.random(mysql_knobs.num_knobs)
        mysql_knobs.apply_action(action)
        pprint(mysql_knobs.knobs)

        for name in mysql_knobs.names:
            knob = mysql_knobs.knobs[name]
            assert(knob.min_value <= knob.value and knob.value <= knob.max_value)
