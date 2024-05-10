from pyrr import Matrix44, Matrix33, Quaternion, Vector3, vector
import sys 
import moderngl
import moderngl_window as mglw
from moderngl_window.integrations.imgui import ModernglWindowRenderer
from moderngl_window.capture.ffmpeg import FFmpegCapture
import numpy as np

import imgui

WORLD_SIZE = 100

class Camera():

    def __init__(self, ratio, position = Vector3([0.0, 0.0, -10.0]), orientation = Vector3([0.0,0.0,1.0])):
        self._zoom_step = 0.1
        self._move_vertically = 0.1
        self._move_horizontally = 0.1
        self._rotate_horizontally = 0.1
        self._rotate_vertically = 0.1

        self._field_of_view_degrees = 60.0
        self._z_near = .01
        self._z_far = 1000
        self._ratio = ratio
        self.build_projection()

        self._camera_position = position/WORLD_SIZE
        self._camera_front = Vector3([0.0, 0.0, 1.0])
        self._camera_up = Vector3([0.0, 1.0, 0.0])
        self._cameras_target = (self._camera_position + self._camera_front)
        self.build_look_at()

    def build_look_at(self):
        self._cameras_target = (self._camera_position + self._camera_front)
        self.mat_lookat = Matrix44.look_at(
            self._camera_position,
            self._cameras_target,
            self._camera_up)
        
    def build_look_at_from_target(self,position):
        self._camera_front = Vector3(position-100*self._camera_position)
        self._camera_front.normalize()
        self._camera_up = Vector3([0,1,0])
        r = self._camera_front.cross(self._camera_up)
        r.normalize()
        self._camera_up = r.cross(self._camera_front)
        self._camera_up.normalize()

        self._cameras_target = (self._camera_position + self._camera_front)
        self.mat_lookat = Matrix44.look_at(
            self._camera_position,
            self._cameras_target,
            self._camera_up) 

    def build_projection(self):
        self.mat_projection = Matrix44.perspective_projection(
            self._field_of_view_degrees,
            self._ratio,
            self._z_near,
            self._z_far)

class Skybox():
    
    def __init__(self, window : mglw.WindowConfig, path : str):
        self.prepare_render(window=window,path=path)
        
    def prepare_render(self,window : mglw.WindowConfig, path : str):
        self.vertices = np.array([
            -1.0,  1.0, -1.0,
            -1.0, -1.0, -1.0,
            1.0, -1.0, -1.0,
            1.0, -1.0, -1.0,
            1.0,  1.0, -1.0,
            -1.0,  1.0, -1.0,

            -1.0, -1.0,  1.0,
            -1.0, -1.0, -1.0,
            -1.0,  1.0, -1.0,
            -1.0,  1.0, -1.0,
            -1.0,  1.0,  1.0,
            -1.0, -1.0,  1.0,

            1.0, -1.0, -1.0,
            1.0, -1.0,  1.0,
            1.0,  1.0,  1.0,
            1.0,  1.0,  1.0,
            1.0,  1.0, -1.0,
            1.0, -1.0, -1.0,

            -1.0, -1.0,  1.0,
            -1.0,  1.0,  1.0,
            1.0,  1.0,  1.0,
            1.0,  1.0,  1.0,
            1.0, -1.0,  1.0,
            -1.0, -1.0,  1.0,

            -1.0,  1.0, -1.0,
            1.0,  1.0, -1.0,
            1.0,  1.0,  1.0,
            1.0,  1.0,  1.0,
            -1.0,  1.0,  1.0,
            -1.0,  1.0, -1.0,

            -1.0, -1.0, -1.0,
            -1.0, -1.0,  1.0,
            1.0, -1.0, -1.0,
            1.0, -1.0, -1.0,
            -1.0, -1.0,  1.0,
            1.0, -1.0,  1.0
        ], dtype='f4')
    
        self.texture = window.load_texture_cube(path,path,path,path,path,path)
        
        self.prog = window.ctx.program(
        vertex_shader='''
            #version 330

            uniform mat4 Mvp;
            
            in vec3 in_vert;

            out vec3 tex_coords;

            void main() {
                tex_coords = in_vert;
                gl_Position = Mvp * vec4(in_vert, 1.0);
            }
        ''',
        fragment_shader='''
            #version 330

            uniform samplerCube skybox;
            
            in vec3 tex_coords;

            out vec4 fragColor;

            void main() {
                fragColor = .9*texture(skybox, tex_coords);
            }
        ''',
        )
        self.vbo = window.ctx.buffer(self.vertices)
        self.vao = window.ctx.simple_vertex_array(self.prog, self.vbo, 'in_vert')
        self.mvp = self.prog['Mvp']
        
    def render(self, context : moderngl.Context, time, camera):
        context.vao = self.vao

        transformation_matrix = Matrix44.identity()

        self.mvp.write((camera.mat_projection * camera.mat_lookat * transformation_matrix).astype('f4'))
        
        self.texture.use()
        context.vao.render()
 

 
class Object():
    def __init__(self, window : mglw.WindowConfig, path, position = np.array([0.0,0.0,0.0])):
        self.position = position
        self.orientation = np.array([0.0,0.0,0.0])
        
        self.velocity = np.array([0.0,0.0,0.0])
        self.angular_velocity = np.array([0.0,0.0,0.0])
        
        self.acceleration = np.array([0.0,0.0,0.0])
        self.angular_acceleration = np.array([0.0,0.0,0.0])
        
        self.prepare_to_render(window,path)
        
    def prepare_to_render(self,window : mglw.WindowConfig, path):
        self.obj = window.load_scene(path)
        self.texture = window.load_texture_2d(sys.path[0]+'/data/bigman_texture.png')
        
        self.prog = window.ctx.program(
            vertex_shader='''
                #version 330

                uniform mat4 Mvp;
                
                in vec3 in_position;
                in vec3 in_normal;
                in vec2 in_texcoord_0;
                
                out vec3 v_vert;
                out vec3 v_norm;
                out vec2 v_text;
                
                void main() {
                    
                    
                    v_vert = in_position;
                    v_norm = in_normal;
                    v_text = in_texcoord_0;
                    
                    gl_Position = Mvp * vec4(in_position, 1.0);
                }
            ''',
            fragment_shader='''
                #version 330
                out vec4 f_color;
                in vec3 v_vert;
                in vec3 v_norm;
                in vec2 v_text;
                
                uniform sampler2D Texture;        

                // material
                uniform vec3 albedo;
                uniform float metallic;
                uniform float roughness;
                uniform float ao;
                
                //lights
                uniform vec3 lightPositions[4];
                uniform vec3 lightColors[4];
                // camera
                uniform vec3 camPos;
                uniform vec3 worldPos;
                
                const float PI = 3.14159265359;
                
                // ----------------------------------------------------------------------------
                float DistributionGGX(vec3 N, vec3 H, float roughness)
                {
                    float a = roughness*roughness;
                    float a2 = a*a;
                    float NdotH = max(dot(N, H), 0.0);
                    float NdotH2 = NdotH*NdotH;

                    float nom   = a2;
                    float denom = (NdotH2 * (a2 - 1.0) + 1.0);
                    denom = PI * denom * denom;

                    return nom / denom;
                }
                // ----------------------------------------------------------------------------
                float GeometrySchlickGGX(float NdotV, float roughness)
                {
                    float r = (roughness + 1.0);
                    float k = (r*r) / 8.0;

                    float nom   = NdotV;
                    float denom = NdotV * (1.0 - k) + k;

                    return nom / denom;
                }
                // ----------------------------------------------------------------------------
                float GeometrySmith(vec3 N, vec3 V, vec3 L, float roughness)
                {
                    float NdotV = max(dot(N, V), 0.0);
                    float NdotL = max(dot(N, L), 0.0);
                    float ggx2 = GeometrySchlickGGX(NdotV, roughness);
                    float ggx1 = GeometrySchlickGGX(NdotL, roughness);

                    return ggx1 * ggx2;
                }
                // ----------------------------------------------------------------------------
                vec3 fresnelSchlick(float cosTheta, vec3 F0)
                {
                    return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
                }
                // ----------------------------------------------------------------------------
                void main()
                {		
                    vec3 WorldPos = v_vert + worldPos;
                    
                    vec3 N = normalize(v_norm);
                    vec3 V = normalize(camPos - WorldPos);

                    
                    // calculate reflectance at normal incidence; if dia-electric (like plastic) use F0 
                    // of 0.04 and if it's a metal, use the albedo color as F0 (metallic workflow)    
                    vec3 F0 = vec3(0.04); 
                    F0 = mix(F0, albedo, metallic);

                    // reflectance equation
                    vec3 Lo = vec3(0.0);
                    for(int i = 0; i < 4; ++i) 
                    {
                        // calculate per-light radiance
                        vec3 L = normalize(lightPositions[i] - WorldPos);
                        vec3 H = normalize(V + L);
                        float distance = length(lightPositions[i] - WorldPos);
                        float attenuation = 1.0 / (distance * distance);
                        vec3 radiance = lightColors[i] * attenuation;

                        // Cook-Torrance BRDF
                        float NDF = DistributionGGX(N, H, roughness);   
                        float G   = GeometrySmith(N, V, L, roughness);      
                        vec3 F    = fresnelSchlick(clamp(dot(H, V), 0.0, 1.0), F0);
                        
                        vec3 numerator    = NDF * G * F; 
                        float denominator = 4.0 * max(dot(N, V), 0.0) * max(dot(N, L), 0.0) + 0.0001; // + 0.0001 to prevent divide by zero
                        vec3 specular = numerator / denominator;
                        
                        // kS is equal to Fresnel
                        vec3 kS = F;
                        // for energy conservation, the diffuse and specular light can't
                        // be above 1.0 (unless the surface emits light); to preserve this
                        // relationship the diffuse component (kD) should equal 1.0 - kS.
                        vec3 kD = vec3(1.0) - kS;
                        // multiply kD by the inverse metalness such that only non-metals 
                        // have diffuse lighting, or a linear blend if partly metal (pure metals
                        // have no diffuse light).
                        kD *= 1.0 - metallic;	  

                        // scale light by NdotL
                        float NdotL = max(dot(N, L), 0.0);        

                        // add to outgoing radiance Lo
                        Lo += (kD * albedo / PI + specular) * radiance * NdotL;  // note that we already multiplied the BRDF by the Fresnel (kS) so we won't multiply by kS again
                    }   
                    
                    // ambient lighting (note that the next IBL tutorial will replace 
                    // this ambient lighting with environment lighting).
                    vec3 ambient = vec3(0.03) * albedo * ao;

                    vec3 color = ambient + Lo;

                    // HDR tonemapping
                    color = color / (color + vec3(1.0));
                    // gamma correct
                    color = pow(color, vec3(1.0/2.2)); 

                    f_color = vec4(color, 1.0);
                }
            ''',
        )

        self.mvp = self.prog['Mvp']

        self.prog['lightPositions'].value = [Vector3((-10.0,-10.0,-10.0))+self.position,
                                             Vector3((10.0,-10.0,-10.0))+self.position,
                                             Vector3((-10.0,10.0,-10.0))+self.position,
                                             Vector3((10.0,10.0,-10.0))+self.position]
        self.prog['lightColors'].value = [Vector3((300.0,300.0,300.0)),Vector3((300.0,300.0,300.0)),Vector3((300.0,300.0,10.0)),Vector3((300.0,300.0,300.0))]
        
        self.prog['albedo'].value = (0.5,0.0,0.0)
        self.prog['roughness'].value = .1
        self.prog['metallic'].value = 0.9
        self.prog['ao'].value = 0.1
        self.vao = self.obj.root_nodes[0].mesh.vao.instance(self.prog)
        

    
    def update_physics(self,time,frame_time, config : dict):
        gravity = np.array([0.0,config['gravity'],0.0])
        
        self.orientation = self.orientation + frame_time*(self.angular_velocity)
        self.angular_velocity = self.angular_velocity + frame_time*(self.angular_acceleration)
        
        self.position = self.position - frame_time*(self.velocity)
        self.velocity = self.velocity - frame_time*(self.acceleration-gravity)
        if config['teleport'] and (int(time*10)+1)%25 == 0:
            self.position = np.random.uniform(-WORLD_SIZE,WORLD_SIZE,3)

        if config["bounce"] and self.position[1]<=0:
            self.position[1] = 0
            self.velocity[1] = -.75*self.velocity[1]
            if self.position[1]<=.1:
                self.velocity[1] = 0
        elif np.abs(self.position[0])>WORLD_SIZE:
            self.position[0] = -1*self.position[0]
        elif np.abs(self.position[1])>WORLD_SIZE:
            self.position[1] = -1*self.position[1]
        elif np.abs(self.position[0])>WORLD_SIZE:
            self.position[2] = -1*self.position[2]
        
    def render(self,context : moderngl.Context, time, camera : Camera, config : dict):
        context.vao = self.vao
        
        self.prog['worldPos'].value = self.position
        self.prog['camPos'].value = camera._camera_position*100
        
    
        scale_matrix = Matrix44.from_scale((1/WORLD_SIZE,1/WORLD_SIZE,1/WORLD_SIZE))
        translation_matrix = Matrix44.from_translation(self.position)
        rotation_quaternion = Quaternion.from_eulers(self.orientation)
        rotation_matrix = Matrix44.from_quaternion(rotation_quaternion)
        transformation_matrix = scale_matrix * translation_matrix * rotation_matrix

        if config['track']:
            camera.build_look_at_from_target(self.position)
        else:
            camera.build_look_at()
        
        self.mvp.write((camera.mat_projection * camera.mat_lookat * transformation_matrix).astype('f4'))
        
        self.texture.use()
        context.vao.render()
    
    


class Simulator(mglw.WindowConfig):
    title = "Loading OBJ"
    
    gl_version = (3, 3)
    title = "Falling Object Simulator"
    window_size = (1280, 720)
    aspect_ratio = 16 / 9
    resizable = True
    
    config = {"cameras": [{"position":[0.0, 10.0, -5.0],"orientation":[0.0,10.0,0.0]},
                          {"position":[10.0, 10.0, -15.0],"orientation":[0.0,10.0,0.0]},
                          {"position":[-10.0, 10.0, -15.0],"orientation":[0.0,10.0,0.0]},]}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config['track'] = False
        self.config["paused"] = False
        self.config["bounce"] = True
        self.config['teleport'] = False
        self.config['gravity'] = 9.8
        imgui.create_context()
        self.imgui = ModernglWindowRenderer(self.wnd)
        self.cameras = []
        for cam_dict in self.config["cameras"]:
            self.cameras.append(Camera(self.aspect_ratio, position = Vector3(cam_dict["position"]),orientation=Vector3(cam_dict["position"])))
        self._active_camera_idx = 0

        self.skybox = Skybox(self,sys.path[0]+'/data/space_skybox_texture.jpg')
        self.obj1 = Object(self,sys.path[0]+'/data/bigman.obj',position = np.array([0.0,10.0,0.0]))
        
        self.capture_contexts = [self.ctx for _ in range(len(self.cameras))]
        self.capture_fbos = [ctx.framebuffer([ctx.texture((1280, 720), 4, dtype='f4')]) for ctx in self.capture_contexts]

        self.videocaptures = [mglw.capture.FFmpegCapture(source=self.capture_fbos[i]) for i in range(len(self.cameras))]
        self.config['capturing video'] = False
        
        

    def capture_render(self,time,frame_time):
        if self.config['capturing video']:
            
            
            for i in range(len(self.cameras)):
                self.capture_fbos[i].use()
                self.capture_fbos[i].clear()
                
                
                self.skybox.render(self.capture_contexts[i],time,self.cameras[i])
                self.obj1.render(self.capture_contexts[i],time,self.cameras[i],self.config)
                self.capture_contexts[i].enable(moderngl.DEPTH_TEST)
                self.videocaptures[i].save()
            self.wnd.use()
        else:  
            pass
        
        
            

    def render(self, time, frame_time):
        self.ctx.screen.use()
        self.ctx.screen.clear()

        self.ctx.enable(moderngl.DEPTH_TEST)
        self.obj1.update_physics(self.config['paused']*time,self.config['paused']*frame_time,self.config)
        self.capture_render(time,frame_time)
        
        self.obj1.render(self,time,self.cameras[self._active_camera_idx],self.config)
        self.skybox.render(self,time,self.cameras[self._active_camera_idx])

        self.render_imgui()
        
        
        
    def render_imgui(self):
        imgui.new_frame()
        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("File", True):
                clicked_quit, selected_quit = imgui.menu_item("Quit", "Cmd+Q", False, True)

                if clicked_quit:
                    exit(0)

                imgui.end_menu()
            imgui.end_main_menu_bar()
        
        imgui.set_next_window_size(200, 600, imgui.FIRST_USE_EVER)
        imgui.set_next_window_position(15, 30, imgui.FIRST_USE_EVER)
        imgui.set_next_window_bg_alpha(0.05)
        imgui.begin("World", True)
        _, self.config['paused'] = imgui.checkbox("Pause", self.config['paused'])
        _, self.config['bounce'] = imgui.checkbox("Bounce", self.config['bounce'])
        _,self.config['gravity'] = imgui.slider_float("Gravity", self.config['gravity'], 0.0, 100.0)

        
        imgui.end()
        
        imgui.set_next_window_size(200, 600, imgui.FIRST_USE_EVER)
        imgui.set_next_window_position(1000, 30, imgui.FIRST_USE_EVER)
        imgui.set_next_window_bg_alpha(0.05)
        imgui.begin("Cameras", True)
        _, self.config['track'] = imgui.checkbox("Track", self.config['track'])
        
        if imgui.button("Start Capture"):
            print('starting capture')
            self.config['capturing video'] = True
            for i,videocapture in enumerate(self.videocaptures):
                
                videocapture.start_capture(
                    filename=f"video_cam_{i}.mp4",
                    framerate=30
                )
        
        if imgui.button("Stop Capture"):
            print('stopping capture')
            self.config['capturing video'] = False
            for videocapture in self.videocaptures:
                videocapture.release()

            for fbo in self.capture_fbos:
                fbo.release()
            self.wnd.use()
            
        _,self._active_camera_idx = imgui.slider_int("Selected Camera", self._active_camera_idx, 0, len(self.cameras)-1)
            
        imgui.end()
        
        imgui.set_next_window_size(300, 300, imgui.FIRST_USE_EVER)
        imgui.set_next_window_position(230, 30, imgui.FIRST_USE_EVER)
        imgui.set_next_window_bg_alpha(0.05)
        imgui.begin("Object", True)
        if imgui.button("Reset Pos"):
            self.obj1.position = np.array([0.0,10.0,0.0])
            self.obj1.velocity = np.array([0.0,0.0,0.0])
            self.obj1.orientation = np.array([0.0,0.0,0.0])
            self.obj1.angular_velocity = np.array([0.0,0.0,0.0])
        if imgui.button("AWAY"):    
            self.obj1.angular_velocity = self.obj1.angular_velocity + np.array([0.0,0.0,0.5])
            self.obj1.velocity = self.obj1.velocity + np.array([0.0,0.0,-2.5])
        _, self.config['teleport'] = imgui.checkbox("Teleport", self.config['teleport'])   
        _,self.obj1.prog['roughness'].value = imgui.slider_float("Roughness", self.obj1.prog['roughness'].value, 0.0, 1.0)
        _,self.obj1.prog['metallic'].value = imgui.slider_float("Metallic", self.obj1.prog['metallic'].value, 0.0, 1.0)
        _,self.obj1.prog['ao'].value = imgui.slider_float("AO", self.obj1.prog['ao'].value, 0.0, 1.0)
        if imgui.button("Random Color"):
            self.obj1.prog['albedo'] = list(np.random.uniform(0,1,3))
        imgui.end()
        
        imgui.render()
        self.imgui.render(imgui.get_draw_data())
        
    def mouse_position_event(self, x, y, dx, dy):
        self.imgui.mouse_position_event(x, y, dx, dy)

    def mouse_drag_event(self, x, y, dx, dy):
        self.imgui.mouse_drag_event(x, y, dx, dy)

    def mouse_scroll_event(self, x_offset, y_offset):
        self.imgui.mouse_scroll_event(x_offset, y_offset)

    def mouse_press_event(self, x, y, button):
        self.imgui.mouse_press_event(x, y, button)

    def mouse_release_event(self, x: int, y: int, button: int):
        self.imgui.mouse_release_event(x, y, button)

    def unicode_char_entered(self, char):
        self.imgui.unicode_char_entered(char)

Simulator.run()
