"""
Main UI window for binding protocol management
"""

import omni.ui as ui
import omni.kit.window.property as window_property
from typing import Dict, Any, Optional, List
import carb

from ..protocol_manager import ProtocolManager, BindingInfo, ConnectionState
from ..binding_parser import BindingParser


class BindingWindow:
    """Main UI window for managing binding protocols"""
    
    def __init__(self, protocol_manager: ProtocolManager, binding_parser: BindingParser):
        self._protocol_manager = protocol_manager
        self._binding_parser = binding_parser
        self._window: Optional[ui.Window] = None
        self._bindings_frame: Optional[ui.Frame] = None
        self._refresh_timer = None
        
        # Register for binding updates
        self._protocol_manager.add_update_callback(self._on_binding_update)
        
        self._create_window()
    
    def _create_window(self):
        """Create the main UI window"""
        self._window = ui.Window("USD Binding Protocols", width=600, height=400)
        
        with self._window.frame:
            with ui.VStack(spacing=5):
                # Header
                ui.Label("USD Binding Protocol Manager", style={"font_size": 18})
                ui.Separator()
                
                # Controls
                with ui.HStack(height=30):
                    ui.Button("Refresh Bindings", clicked_fn=self._refresh_bindings, width=120)
                    ui.Spacer()
                    ui.Button("Start All Streaming", clicked_fn=self._start_all_streaming, width=120)
                    ui.Button("Stop All Streaming", clicked_fn=self._stop_all_streaming, width=120)
                
                ui.Separator()
                
                # Bindings list
                ui.Label("Active Bindings:", style={"font_size": 14})
                
                # Scrollable frame for bindings
                scroll_frame = ui.ScrollingFrame(
                    height=300,
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_ON
                )
                
                with scroll_frame:
                    self._bindings_frame = ui.VStack(spacing=2)
        
        # Initial refresh
        self._refresh_bindings()
        
        # Set up periodic refresh
        self._setup_refresh_timer()
    
    def _setup_refresh_timer(self):
        """Set up timer for periodic UI refresh"""
        import asyncio
        
        async def refresh_loop():
            while self._window and not self._window.frame.destroyed:
                self._refresh_bindings()
                await asyncio.sleep(2.0)  # Refresh every 2 seconds
        
        if hasattr(asyncio, 'create_task'):
            self._refresh_timer = asyncio.create_task(refresh_loop())
    
    def _refresh_bindings(self):
        """Refresh the bindings display"""
        if not self._bindings_frame or self._bindings_frame.destroyed:
            return
        
        # Clear existing content
        self._bindings_frame.clear()
        
        try:
            bindings = self._protocol_manager.get_bindings()
            
            if not bindings:
                with self._bindings_frame:
                    ui.Label("No bindings found. Open a USD stage with BindingAPI to see bindings here.")
                return
            
            # Group bindings by prim
            prim_bindings: Dict[str, List[BindingInfo]] = {}
            for binding_info in bindings.values():
                prim_path = binding_info.prim_path
                if prim_path not in prim_bindings:
                    prim_bindings[prim_path] = []
                prim_bindings[prim_path].append(binding_info)
            
            # Display bindings grouped by prim
            with self._bindings_frame:
                for prim_path, prim_binding_list in prim_bindings.items():
                    self._create_prim_binding_section(prim_path, prim_binding_list)
                    
        except Exception as e:
            carb.log_error(f"[BindingWindow] Error refreshing bindings: {e}")
            with self._bindings_frame:
                ui.Label(f"Error refreshing bindings: {e}", style={"color": 0xFF0000FF})
    
    def _create_prim_binding_section(self, prim_path: str, bindings: List[BindingInfo]):
        """Create UI section for a prim's bindings"""
        with ui.Frame(style={"border_width": 1, "border_color": 0xFF555555}):
            with ui.VStack(spacing=3):
                # Prim header
                with ui.HStack(height=25):
                    ui.Label(f"Prim: {prim_path}", style={"font_size": 12, "font_weight": "bold"})
                    ui.Spacer()
                
                # Bindings for this prim
                for binding_info in bindings:
                    self._create_binding_item(binding_info)
    
    def _create_binding_item(self, binding_info: BindingInfo):
        """Create UI item for a single binding"""
        with ui.Frame(style={"border_width": 1, "border_color": 0xFF333333, "margin": 2}):
            with ui.VStack(spacing=2):
                # Binding header
                with ui.HStack(height=20):
                    ui.Label(f"{binding_info.attr_name}", style={"font_size": 11, "font_weight": "bold"})
                    ui.Spacer()
                    
                    # Status indicator
                    status_color = self._get_status_color(binding_info.state)
                    ui.Rectangle(width=12, height=12, style={"background_color": status_color})
                    ui.Label(binding_info.state.value, style={"font_size": 10})
                
                # Binding details
                with ui.HStack(height=15):
                    ui.Label(f"Protocol: {binding_info.protocol}", style={"font_size": 10})
                    ui.Spacer()
                    ui.Label(f"Operation: {binding_info.operation}", style={"font_size": 10})
                
                # URI/endpoint
                uri = binding_info.config.get("uri", "N/A")
                if len(uri) > 50:
                    uri = uri[:47] + "..."
                ui.Label(f"URI: {uri}", style={"font_size": 9, "color": 0xFF888888})
                
                # Last value (if available)
                if binding_info.last_value is not None:
                    value_str = str(binding_info.last_value)
                    if len(value_str) > 60:
                        value_str = value_str[:57] + "..."
                    ui.Label(f"Last Value: {value_str}", style={"font_size": 9, "color": 0xFF00AA00})
                
                # Error (if any)
                if binding_info.last_error:
                    error_str = binding_info.last_error
                    if len(error_str) > 60:
                        error_str = error_str[:57] + "..."
                    ui.Label(f"Error: {error_str}", style={"font_size": 9, "color": 0xFF0000AA})
                
                # Controls
                with ui.HStack(height=20):
                    if binding_info.operation == "stream":
                        if binding_info.state == ConnectionState.CONNECTED:
                            ui.Button("Stop", clicked_fn=lambda b=binding_info: self._stop_binding(b), width=50, height=18)
                        else:
                            ui.Button("Start", clicked_fn=lambda b=binding_info: self._start_binding(b), width=50, height=18)
                    else:
                        ui.Button("Read", clicked_fn=lambda b=binding_info: self._read_binding(b), width=50, height=18)
                    
                    ui.Spacer()
                    ui.Button("Details", clicked_fn=lambda b=binding_info: self._show_binding_details(b), width=60, height=18)
    
    def _get_status_color(self, state: ConnectionState) -> int:
        """Get color for connection state"""
        if state == ConnectionState.CONNECTED:
            return 0xFF00AA00  # Green
        elif state == ConnectionState.CONNECTING:
            return 0xFFAAAA00  # Yellow
        elif state == ConnectionState.ERROR:
            return 0xFFAA0000  # Red
        else:
            return 0xFF666666  # Gray
    
    def _start_binding(self, binding_info: BindingInfo):
        """Start a specific binding"""
        import asyncio
        binding_key = f"{binding_info.prim_path}.{binding_info.attr_name}"
        asyncio.create_task(self._protocol_manager._connect_binding(binding_key))
    
    def _stop_binding(self, binding_info: BindingInfo):
        """Stop a specific binding"""
        import asyncio
        binding_key = f"{binding_info.prim_path}.{binding_info.attr_name}"
        asyncio.create_task(self._protocol_manager._disconnect_binding(binding_key))
    
    def _read_binding(self, binding_info: BindingInfo):
        """Trigger a read for a specific binding"""
        import asyncio
        if binding_info.client:
            async def do_read():
                try:
                    value = await binding_info.client.read(binding_info.config)
                    await self._protocol_manager._update_attribute_value(binding_info, value)
                except Exception as e:
                    carb.log_error(f"[BindingWindow] Error reading binding: {e}")
            
            asyncio.create_task(do_read())
    
    def _show_binding_details(self, binding_info: BindingInfo):
        """Show detailed information about a binding"""
        details_window = ui.Window(f"Binding Details - {binding_info.attr_name}", width=500, height=400)
        
        with details_window.frame:
            with ui.VStack(spacing=5):
                ui.Label(f"Binding Details: {binding_info.prim_path}.{binding_info.attr_name}", 
                        style={"font_size": 14, "font_weight": "bold"})
                ui.Separator()
                
                # Configuration details
                ui.Label("Configuration:", style={"font_size": 12, "font_weight": "bold"})
                
                scroll_frame = ui.ScrollingFrame(height=250)
                with scroll_frame:
                    with ui.VStack(spacing=2):
                        for key, value in binding_info.config.items():
                            if not key.startswith("_"):  # Skip internal fields
                                with ui.HStack():
                                    ui.Label(f"{key}:", width=120, style={"font_size": 10})
                                    ui.Label(str(value), style={"font_size": 10, "color": 0xFF888888})
                
                # Close button
                ui.Button("Close", clicked_fn=lambda: details_window.frame.destroy(), height=25)
    
    def _start_all_streaming(self):
        """Start all streaming connections"""
        import asyncio
        asyncio.create_task(self._protocol_manager.start_streaming_connections())
    
    def _stop_all_streaming(self):
        """Stop all streaming connections"""
        import asyncio
        asyncio.create_task(self._protocol_manager.stop_streaming_connections())
    
    def _on_binding_update(self, prim_path: str, attr_name: str, value: Any):
        """Callback for when a binding value is updated"""
        # UI will be refreshed by the timer, so we don't need to do anything here
        pass
    
    def destroy(self):
        """Clean up the window"""
        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None
        
        if self._protocol_manager:
            self._protocol_manager.remove_update_callback(self._on_binding_update)
        
        if self._window:
            self._window.frame.destroy()
            self._window = None
