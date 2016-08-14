"""
DataGeneratorInterface
"""
import sys
from threading import Condition


class DataGeneratorInterface(object):
    """
    DataGeneratorInterface: interface for parallelisation of dsg generation
    """

    __slots__ = [
        # the application vertex of this vertex
        "_associated_vertex",

        # the vertex to be considered for dsg
        "_vertex",

        # the placement of the vertex to be considered for dsg
        "_placement",

        # the machine graph
        "_machine_graph",

        # the application graph
        "_application_graph",

        # the routing info objects
        "_routing_infos",

        # the string that represnets the ipaddress that these dsg's are aimed at
        "_hostname",

        # the graph mapper object
        "_graph_mapper",

        # report folder directory
        "_report_default_directory",

        # set of iptags
        "_ip_tags",

        # set of reverse iptags
        "_reverse_ip_tags",

        # the progress bar object
        "_progress_bar",

        # bool flag for writing human readable specs
        "_write_text_specs",

        # the folder to store app data
        "_application_run_time_folder",

        # boolean flag for when this has finished writing
        "_done",

        # the exception
        "_exception",

        # the stack trace for the exception
        "_stack_trace",

        # lock for wiriting file folder. To stop deleting it and losing data
        "_wait_condition"

    ]

    def __init__(self, associated_vertex, vertex, placement,
                 machine_graph, application_graph, routing_infos,
                 hostname, graph_mapper, report_default_directory, ip_tags,
                 reverse_ip_tags, write_text_specs,
                 application_run_time_folder, progress_bar):
        self._associated_vertex = associated_vertex
        self._vertex = vertex
        self._placement = placement
        self._machine_graph = machine_graph
        self._application_graph = application_graph
        self._routing_infos = routing_infos
        self._hostname = hostname
        self._graph_mapper = graph_mapper
        self._report_default_directory = report_default_directory
        self._ip_tags = ip_tags
        self._reverse_ip_tags = reverse_ip_tags
        self._progress_bar = progress_bar
        self._write_text_specs = write_text_specs
        self._application_run_time_folder = application_run_time_folder
        self._done = False
        self._exception = None
        self._stack_trace = None
        self._wait_condition = Condition()

    def start(self):
        """

        :return:
        """
        try:
            self._associated_vertex.generate_data_spec(
                self._vertex, self._placement, self._machine_graph,
                self._application_graph, self._routing_infos, self._hostname,
                self._graph_mapper, self._report_default_directory,
                self._ip_tags, self._reverse_ip_tags, self._write_text_specs,
                self._application_run_time_folder)
            self._progress_bar.update()
            self._wait_condition.acquire()
            self._done = True
            self._wait_condition.notify_all()
            self._wait_condition.release()
        except Exception as e:
            self._wait_condition.acquire()
            self._exception = e
            self._stack_trace = sys.exc_info()[2]
            self._wait_condition.notify_all()
            self._wait_condition.release()

    def wait_for_finish(self):
        """

        :return:
        """
        self._wait_condition.acquire()
        while not self._done and self._exception is None:
            self._wait_condition.wait()
        self._wait_condition.release()
        if self._exception is not None:
            raise self._exception, None, self._stack_trace

    def __str__(self):
        return "dgi for placement {}.{}.{}".format(self._placement.x,
                                                   self._placement.y,
                                                   self._placement.p)

    def __repr__(self):
        return self.__str__()
