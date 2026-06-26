
_BEATRICE_SKINNED_CACHE: dict = {}

_HEARTLESS_SKINNED_CACHE: dict = {}
_AERIALKNOCKER_SKINNED_CACHE: dict = {}
_EMILIA_SKINNED_CACHE:        dict = {}
_MARLUXIA_SKINNED_CACHE:      dict = {}

class Caches:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.obj_cache: dict[str, list] = {}
            self.skinned_cache: dict = {}
            self._initialized = True