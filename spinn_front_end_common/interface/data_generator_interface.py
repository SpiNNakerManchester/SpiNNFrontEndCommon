import traceback


class DataGeneratorInterface(object):

    def __init__(self, associated_vertex, subvertex, placement,
                 partitioned_graph, partitionable_graph, routing_infos,
                 hostname, graph_mapper, report_default_directory,
                 write_text_specs, application_run_time_report_folder,
                 progress_bar):
        self._associated_vertex = associated_vertex
        self._subvertex = subvertex
        self._placement = placement
        self._partitioned_graph = partitioned_graph
        self._partitionable_graph = partitionable_graph
        self._routing_infos = routing_infos
        self._hostname = hostname
        self._graph_mapper = graph_mapper
        self._report_default_directory = report_default_directory
        self._write_text_specs = write_text_specs
        self._application_run_time_report_folder =\
            application_run_time_report_folder
        self._progress_bar = progress_bar

    def start(self):
        try:
            self._associated_vertex.generate_data_spec(
                self._subvertex, self._placement, self._partitioned_graph,
                self._partitionable_graph, self._routing_infos, self._hostname,
                self._graph_mapper, self._report_default_directory,
                self._write_text_specs,
                self._application_run_time_report_folder)
            if self._progress_bar is not None:
                self._progress_bar.update()
        except Exception as e:
            print "something died for {} with error {}".format(
                self.__str__(), e.message)
            traceback.print_exc()

    def __str__(self):
        return "dgi for placement {}.{}.{}".format(self._placement.x,
                                                   self._placement.y,
                                                   self._placement.p)

    def __repr__(self):
        return self.__str__()