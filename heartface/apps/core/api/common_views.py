class ExtendViewSet(object):
    permission_map = {}
    serializer_class_map = {}

    def get_serializer_class(self):
        ser = self.serializer_class_map.get(self.action, None)
        self.serializer_class = ser or self.serializer_class
        return super().get_serializer_class()

    def get_permissions(self):
        perms = self.permission_map.get(self.action, None)
        if perms and not isinstance(perms, (tuple, list)):
            perms = [perms, ]
        self.permission_classes = perms or self.permission_classes
        return super().get_permissions()
