"""
Main extension module for USD Binding Protocol handler
"""

import asyncio
import weakref
from typing import Dict, Any, Optional, Set
import omni.ext
import omni.usd
import omni.timeline
from pxr import Usd, UsdGeom, Sdf
import carb

from .protocol_manager import ProtocolManager
from .binding_parser import BindingParser
from .ui.binding_window import BindingWindow


class BindingProtocolExtension(omni.ext.IExt):
    """Main extension class for USD Binding Protocol handler"""

    def __init__(self):
        super().__init__()
        self._protocol_manager: Optional[ProtocolManager] = None
        self._binding_parser: Optional[BindingParser] = None
        self._binding_window: Optional[BindingWindow] = None
        self._stage_listener: Optional[Usd.StageWeak] = None
        self._timeline_sub = None
        self._usd_context = None
        self._bound_prims: Set[str] = set()
        
    def on_startup(self, ext_id: str):
        """Called when the extension is starting up"""
        carb.log_info(f"[omni.binding.protocol] Starting USD Binding Protocol Extension")
        
        # Initialize core components
        self._protocol_manager = ProtocolManager()
        self._binding_parser = BindingParser()
        
        # Get USD context
        self._usd_context = omni.usd.get_context()
        
        # Subscribe to stage events
        self._stage_event_sub = self._usd_context.get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event, name="binding_protocol_stage_event"
        )
        
        # Subscribe to timeline events for streaming protocols
        timeline = omni.timeline.get_timeline_interface()
        self._timeline_sub = timeline.get_timeline_event_stream().create_subscription_to_pop(
            self._on_timeline_event, name="binding_protocol_timeline"
        )
        
        # Create UI window
        self._binding_window = BindingWindow(self._protocol_manager, self._binding_parser)
        
        carb.log_info(f"[omni.binding.protocol] Extension started successfully")
    
    def on_shutdown(self):
        """Called when the extension is shutting down"""
        carb.log_info(f"[omni.binding.protocol] Shutting down USD Binding Protocol Extension")
        
        # Clean up subscriptions
        if self._stage_event_sub:
            self._stage_event_sub.unsubscribe()
            self._stage_event_sub = None
            
        if self._timeline_sub:
            self._timeline_sub.unsubscribe()
            self._timeline_sub = None
        
        # Stop all active connections
        if self._protocol_manager:
            asyncio.create_task(self._protocol_manager.shutdown())
            self._protocol_manager = None
        
        # Clean up UI
        if self._binding_window:
            self._binding_window.destroy()
            self._binding_window = None
            
        self._binding_parser = None
        self._usd_context = None
        self._bound_prims.clear()
        
        carb.log_info(f"[omni.binding.protocol] Extension shutdown complete")
    
    def _on_stage_event(self, event):
        """Handle USD stage events"""
        if event.type == int(omni.usd.StageEventType.OPENED):
            self._on_stage_opened()
        elif event.type == int(omni.usd.StageEventType.CLOSING):
            self._on_stage_closing()
    
    def _on_stage_opened(self):
        """Handle stage opened event"""
        stage = self._usd_context.get_stage()
        if not stage:
            return
            
        carb.log_info(f"[omni.binding.protocol] Stage opened, scanning for bindings")
        
        # Scan stage for binding metadata
        self._scan_stage_for_bindings(stage)
    
    def _on_stage_closing(self):
        """Handle stage closing event"""
        carb.log_info(f"[omni.binding.protocol] Stage closing, stopping all bindings")
        
        # Stop all active connections
        if self._protocol_manager:
            asyncio.create_task(self._protocol_manager.stop_all_connections())
        
        self._bound_prims.clear()
    
    def _on_timeline_event(self, event):
        """Handle timeline events for streaming protocols"""
        if not self._protocol_manager:
            return
            
        if event.type == int(omni.timeline.TimelineEventType.PLAY):
            asyncio.create_task(self._protocol_manager.start_streaming_connections())
        elif event.type == int(omni.timeline.TimelineEventType.STOP):
            asyncio.create_task(self._protocol_manager.stop_streaming_connections())
    
    def _scan_stage_for_bindings(self, stage: Usd.Stage):
        """Scan the stage for prims with binding metadata"""
        if not stage or not self._binding_parser:
            return
        
        try:
            # Traverse all prims in the stage
            for prim in stage.Traverse():
                if not prim.IsValid():
                    continue
                
                # Check if prim has BindingAPI applied
                if prim.HasAPI(Usd.SchemaBase):
                    api_schemas = prim.GetAppliedSchemas()
                    if "BindingAPI" in api_schemas:
                        self._process_binding_prim(prim)
                
                # Check attributes for binding metadata
                for attr in prim.GetAttributes():
                    if self._has_binding_metadata(attr):
                        self._process_binding_attribute(prim, attr)
                        
        except Exception as e:
            carb.log_error(f"[omni.binding.protocol] Error scanning stage: {e}")
    
    def _has_binding_metadata(self, attr: Usd.Attribute) -> bool:
        """Check if attribute has binding metadata"""
        if not attr.IsValid():
            return False
            
        # Look for binding: metadata
        for key in attr.GetMetadata().keys():
            if key.startswith("binding:"):
                return True
        return False
    
    def _process_binding_prim(self, prim: Usd.Prim):
        """Process a prim with BindingAPI"""
        try:
            prim_path = str(prim.GetPath())
            if prim_path in self._bound_prims:
                return
                
            carb.log_info(f"[omni.binding.protocol] Processing binding prim: {prim_path}")
            
            # Parse context and auth defaults
            context = self._binding_parser.parse_context(prim)
            auth_defaults = self._binding_parser.parse_auth_defaults(prim)
            
            # Store context in protocol manager
            if self._protocol_manager:
                self._protocol_manager.set_prim_context(prim_path, context, auth_defaults)
            
            self._bound_prims.add(prim_path)
            
        except Exception as e:
            carb.log_error(f"[omni.binding.protocol] Error processing binding prim {prim.GetPath()}: {e}")
    
    def _process_binding_attribute(self, prim: Usd.Prim, attr: Usd.Attribute):
        """Process an attribute with binding metadata"""
        try:
            prim_path = str(prim.GetPath())
            attr_name = attr.GetName()
            
            carb.log_info(f"[omni.binding.protocol] Processing binding attribute: {prim_path}.{attr_name}")
            
            # Parse binding metadata
            binding_config = self._binding_parser.parse_attribute_binding(prim, attr)
            if not binding_config:
                return
            
            # Register with protocol manager
            if self._protocol_manager:
                asyncio.create_task(
                    self._protocol_manager.register_binding(prim_path, attr_name, binding_config)
                )
                
        except Exception as e:
            carb.log_error(f"[omni.binding.protocol] Error processing binding attribute {prim.GetPath()}.{attr.GetName()}: {e}")
