from functools import partial
import numpy as np

from nnlib import nnlib
from models import ModelBase
from facelib import FaceType
from samplelib import *
from interact import interact as io

#SAE - Styled AutoEncoder
class SAEModel(ModelBase):

    encoderH5 = 'encoder.h5'
    inter_BH5 = 'inter_B.h5'
    inter_ABH5 = 'inter_AB.h5'
    decoderH5 = 'decoder.h5'
    decodermH5 = 'decoderm.h5'

    decoder_srcH5 = 'decoder_src.h5'
    decoder_srcmH5 = 'decoder_srcm.h5'
    decoder_dstH5 = 'decoder_dst.h5'
    decoder_dstmH5 = 'decoder_dstm.h5'

    #override
    def onInitializeOptions(self, is_first_run, ask_override):
        yn_str = {True:'y',False:'n'}

        default_resolution = 128
        default_archi = 'df'
        default_face_type = 'f'

        if is_first_run:
            resolution = io.input_int("分辨率 ( 64-256 ?:帮助 跳过:128) : ", default_resolution, help_message="更多的分辨率需要更多的虚拟内存和时间来训练,值将调整为16的倍数.")
            resolution = np.clip (resolution, 64, 256)
            while np.modf(resolution / 16)[0] != 0.0:
                resolution -= 1
            self.options['resolution'] = resolution

            self.options['face_type'] = io.input_str("半脸或全脸? (h/f, ?:帮助 默认:f) : ", default_face_type, ['h', 'f'],help_message="半张脸有更好的分辨率,但是覆盖了更少的脸颊区域.").lower()
            self.options['learn_mask'] = io.input_bool("学习面具? (y/n, ?:帮助 默认:y) : ", True,help_message="学习面具可以帮助模型识别人脸方向,学习没有面具可以减少模型大小，在这种情况下转换器被迫使用“未预测面具”,不会顺利的预测.具有样式值的模型无需面具即可学习,生成相同的质量结果.")
        else:
            self.options['resolution'] = self.options.get('resolution', default_resolution)
            self.options['face_type'] = self.options.get('face_type', default_face_type)
            self.options['learn_mask'] = self.options.get('learn_mask', True)


        if (is_first_run or ask_override) and 'tensorflow' in self.device_config.backend:
            def_optimizer_mode = self.options.get('optimizer_mode', 1)
            self.options['optimizer_mode'] = io.input_int("优化器模式? ( 1,2,3 ?:帮助 默认:%d) : " % (def_optimizer_mode),def_optimizer_mode,help_message="1 -没有变化.2 -允许你训练x2更大的网络消耗RAM.3 -允许你训练x3更大的网络消耗大量的内存和更慢的速度,这取决于CPU的功率.")
        else:
            self.options['optimizer_mode'] = self.options.get('optimizer_mode', 1)

        if is_first_run:
            self.options['archi'] = io.input_str("AE架构 (df, liae ?:帮助 默认:%s) : " % (default_archi), default_archi, ['df', 'liae'], help_message="'df'让脸看起来更自然.'liae'可以修复过于不同的脸型.").lower()  # -s version is slower, but has decreased change to collapse.
        else:
            self.options['archi'] = self.options.get('archi', default_archi)

        default_ae_dims = 256 if 'liae' in self.options['archi'] else 512
        default_e_ch_dims = 42
        default_d_ch_dims = default_e_ch_dims // 2
        def_ca_weights = False

        if is_first_run:
            self.options['ae_dims'] = np.clip(
                io.input_int("AutoEncoder变暗 (32-1024 ?:帮助 默认:%d) : " % (default_ae_dims), default_ae_dims,
                             help_message="所有的面部信息将被压缩到AE dims.如果AE的暗度不够,那么例如闭上眼睛将无法识别.越暗越好,但是需要更多的VRAM,您可以微调模型大小,以适应您的GPU."),
                32, 1024)
            self.options['e_ch_dims'] = np.clip(
                io.input_int("每个通道的编码器变暗 (21-85 ?:帮助 默认:%d) : " % (default_e_ch_dims), default_e_ch_dims,
                             help_message="更多的编码模糊有助于识别更多的面部特征,但需要更多的VRAM.您可以微调模型大小,以适应您的GPU."), 21, 85)
            default_d_ch_dims = self.options['e_ch_dims'] // 2
            self.options['d_ch_dims'] = np.clip(
                io.input_int("每个信道的解码器变暗 (10-85 ?:帮助 默认:%d) : " % (default_d_ch_dims), default_d_ch_dims,
                             help_message="更多的解码器变暗有助于获得更好的细节,但需要更多的VRAM.您可以微调模型大小,以适应您的GPU."), 10, 85)
            self.options['multiscale_decoder'] = io.input_bool("多尺度解码器? (y/n, ?:帮助 默认:n) : ", False,
                                                               help_message="多尺度解码器有助于获得更好的细节.")
            self.options['ca_weights'] = io.input_bool("使用CA权重? (y/n, ?:帮助 默认: %s ) : " % (yn_str[def_ca_weights]),
                                                       def_ca_weights,
                                                       help_message="使用'卷积感知'权重初始化网络.这可能有助于实现更高精度的模型,但在第一次运行时会消耗时间.")
        else:
            self.options['ae_dims'] = self.options.get('ae_dims', default_ae_dims)
            self.options['e_ch_dims'] = self.options.get('e_ch_dims', default_e_ch_dims)
            self.options['d_ch_dims'] = self.options.get('d_ch_dims', default_d_ch_dims)
            self.options['multiscale_decoder'] = self.options.get('multiscale_decoder', False)
            self.options['ca_weights'] = self.options.get('ca_weights', def_ca_weights)

        default_face_style_power = 0.0
        default_bg_style_power = 0.0
        if is_first_run or ask_override:
            def_pixel_loss = self.options.get('pixel_loss', False)
            self.options['pixel_loss'] = io.input_bool("使用像素损失? (y/n, ?:帮助 默认: %s ) : " % (yn_str[def_pixel_loss]),def_pixel_loss, help_message="像素损失可能有助于增强精细细节和稳定面部颜色.只有在质量没有随着时间的推移而提高时才使用它.过早启用此选项会增加模型崩溃的可能性.")

            default_face_style_power = default_face_style_power if is_first_run else self.options.get('face_style_power', default_face_style_power)
            self.options['face_style_power'] = np.clip(io.input_number("面部风格细节 ( 0.0 .. 100.0 ?:帮助 默认:%.2f) : " % (default_face_style_power),default_face_style_power,help_message="学习转换面部风格细节,如光线和颜色条件.警告:只有在10k打圈后才启用,当预测的面部足够清晰时才能开始学习样式.从0.1值开始,并检查历史更改.启用此选项将增加模型崩溃的几率."),0.0, 100.0)

            default_bg_style_power = default_bg_style_power if is_first_run else self.options.get('bg_style_power', default_bg_style_power)
            self.options['bg_style_power'] = np.clip( io.input_number("脸部周围细节 ( 0.0 .. 100.0 ?:帮助 默认:%.2f) : " % (default_bg_style_power),default_bg_style_power, help_message="学会在脸部周围传递图像.这可以使脸更像dst.启用此选项将加大模型崩溃的几率."), 0.0, 100.0)

            default_apply_random_ct = False if is_first_run else self.options.get('apply_random_ct', False)
            self.options['apply_random_ct'] = io.input_bool ("应用随机颜色转移到src面板? (y/n, ?:帮助 默认:%s) : " % (yn_str[default_apply_random_ct]), default_apply_random_ct, help_message="通过对随机dst样品进行LCT颜色转移，提高src样品的多样性。它类似于“face_style”学习，但更精确的颜色转换，没有模型崩溃的风险，也不需要额外的GPU资源，但训练时间可能会更长，因为src的faceset正在变得更加多样化。")
        else:
            self.options['pixel_loss'] = self.options.get('pixel_loss', False)
            self.options['face_style_power'] = self.options.get('face_style_power', default_face_style_power)
            self.options['bg_style_power'] = self.options.get('bg_style_power', default_bg_style_power)
            self.options['apply_random_ct'] = self.options.get('apply_random_ct', False)

        if is_first_run:
            self.options['pretrain'] = io.input_bool("预训练模型? (y/n, ?:帮助 默认:n) : ", False,help_message="用大量不同的面对模型进行预训练.这种技术可以帮助训练具有过不同脸型和src/dst数据光照条件的假人.脸看起来更像变形的.为了减少变形效果,一些模型文件将被初始化,但是在pretrain: LIAE: inter_AB之后不会被更新.h5 DF: encoder.h5.你对模特的预训练时间越长,你的脸看起来就会越变形.之后,保存并再次运行培训.")
        else:
            self.options['pretrain'] = False

    #override
    def onInitialize(self):
        exec(nnlib.import_all(), locals(), globals())
        SAEModel.initialize_nn_functions()
        self.set_vram_batch_requirements({1.5:4})

        resolution = self.options['resolution']
        ae_dims = self.options['ae_dims']
        e_ch_dims = self.options['e_ch_dims']
        d_ch_dims = self.options['d_ch_dims']
        self.pretrain = self.options['pretrain'] = self.options.get('pretrain', False)
        if not self.pretrain:
            self.options.pop('pretrain')

        d_residual_blocks = True
        bgr_shape = (resolution, resolution, 3)
        mask_shape = (resolution, resolution, 1)

        self.ms_count = ms_count = 3 if (self.options['multiscale_decoder']) else 1

        apply_random_ct = self.options.get('apply_random_ct', False)
        masked_training = True

        warped_src = Input(bgr_shape)
        target_src = Input(bgr_shape)
        target_srcm = Input(mask_shape)

        warped_dst = Input(bgr_shape)
        target_dst = Input(bgr_shape)
        target_dstm = Input(mask_shape)

        target_src_ar = [ Input ( ( bgr_shape[0] // (2**i) ,)*2 + (bgr_shape[-1],) ) for i in range(ms_count-1, -1, -1)]
        target_srcm_ar = [ Input ( ( mask_shape[0] // (2**i) ,)*2 + (mask_shape[-1],) ) for i in range(ms_count-1, -1, -1)]
        target_dst_ar  = [ Input ( ( bgr_shape[0] // (2**i) ,)*2 + (bgr_shape[-1],) ) for i in range(ms_count-1, -1, -1)]
        target_dstm_ar = [ Input ( ( mask_shape[0] // (2**i) ,)*2 + (mask_shape[-1],) ) for i in range(ms_count-1, -1, -1)]

        common_flow_kwargs = { 'padding': 'zero',
                               'norm': '',
                               'act':'' }
        models_list = []
        weights_to_load = []
        if 'liae' in self.options['archi']:
            self.encoder = modelify(SAEModel.LIAEEncFlow(resolution, ch_dims=e_ch_dims, **common_flow_kwargs)  ) (Input(bgr_shape))

            enc_output_Inputs = [ Input(K.int_shape(x)[1:]) for x in self.encoder.outputs ]

            self.inter_B = modelify(SAEModel.LIAEInterFlow(resolution, ae_dims=ae_dims, **common_flow_kwargs)) (enc_output_Inputs)
            self.inter_AB = modelify(SAEModel.LIAEInterFlow(resolution, ae_dims=ae_dims, **common_flow_kwargs)) (enc_output_Inputs)

            inter_output_Inputs = [ Input( np.array(K.int_shape(x)[1:])*(1,1,2) ) for x in self.inter_B.outputs ]

            self.decoder = modelify(SAEModel.LIAEDecFlow (bgr_shape[2],ch_dims=d_ch_dims, multiscale_count=self.ms_count, add_residual_blocks=d_residual_blocks, **common_flow_kwargs)) (inter_output_Inputs)
            models_list += [self.encoder, self.inter_B, self.inter_AB, self.decoder]

            if self.options['learn_mask']:
                self.decoderm = modelify(SAEModel.LIAEDecFlow (mask_shape[2],ch_dims=d_ch_dims, **common_flow_kwargs)) (inter_output_Inputs)
                models_list += [self.decoderm]

            if not self.is_first_run():
                weights_to_load += [  [self.encoder , 'encoder.h5'],
                                      [self.inter_B , 'inter_B.h5'],
                                      [self.inter_AB, 'inter_AB.h5'],
                                      [self.decoder , 'decoder.h5'],
                                    ]
                if self.options['learn_mask']:
                    weights_to_load += [ [self.decoderm, 'decoderm.h5'] ]

            warped_src_code = self.encoder (warped_src)
            warped_src_inter_AB_code = self.inter_AB (warped_src_code)
            warped_src_inter_code = Concatenate()([warped_src_inter_AB_code,warped_src_inter_AB_code])

            warped_dst_code = self.encoder (warped_dst)
            warped_dst_inter_B_code = self.inter_B (warped_dst_code)
            warped_dst_inter_AB_code = self.inter_AB (warped_dst_code)
            warped_dst_inter_code = Concatenate()([warped_dst_inter_B_code,warped_dst_inter_AB_code])

            warped_src_dst_inter_code = Concatenate()([warped_dst_inter_AB_code,warped_dst_inter_AB_code])

            pred_src_src = self.decoder(warped_src_inter_code)
            pred_dst_dst = self.decoder(warped_dst_inter_code)
            pred_src_dst = self.decoder(warped_src_dst_inter_code)

            if self.options['learn_mask']:
                pred_src_srcm = self.decoderm(warped_src_inter_code)
                pred_dst_dstm = self.decoderm(warped_dst_inter_code)
                pred_src_dstm = self.decoderm(warped_src_dst_inter_code)

        elif 'df' in self.options['archi']:
            self.encoder = modelify(SAEModel.DFEncFlow(resolution, ae_dims=ae_dims, ch_dims=e_ch_dims, **common_flow_kwargs)  ) (Input(bgr_shape))

            dec_Inputs = [ Input(K.int_shape(x)[1:]) for x in self.encoder.outputs ]

            self.decoder_src = modelify(SAEModel.DFDecFlow (bgr_shape[2],ch_dims=d_ch_dims, multiscale_count=self.ms_count, add_residual_blocks=d_residual_blocks, **common_flow_kwargs )) (dec_Inputs)
            self.decoder_dst = modelify(SAEModel.DFDecFlow (bgr_shape[2],ch_dims=d_ch_dims, multiscale_count=self.ms_count, add_residual_blocks=d_residual_blocks, **common_flow_kwargs )) (dec_Inputs)
            models_list += [self.encoder, self.decoder_src, self.decoder_dst]

            if self.options['learn_mask']:
                self.decoder_srcm = modelify(SAEModel.DFDecFlow (mask_shape[2],ch_dims=d_ch_dims, **common_flow_kwargs )) (dec_Inputs)
                self.decoder_dstm = modelify(SAEModel.DFDecFlow (mask_shape[2],ch_dims=d_ch_dims, **common_flow_kwargs )) (dec_Inputs)
                models_list += [self.decoder_srcm, self.decoder_dstm]

            if not self.is_first_run():
                weights_to_load += [  [self.encoder    , 'encoder.h5'],
                                      [self.decoder_src, 'decoder_src.h5'],
                                      [self.decoder_dst, 'decoder_dst.h5']
                                    ]
                if self.options['learn_mask']:
                    weights_to_load += [ [self.decoder_srcm, 'decoder_srcm.h5'],
                                         [self.decoder_dstm, 'decoder_dstm.h5'],
                                       ]

            warped_src_code = self.encoder (warped_src)
            warped_dst_code = self.encoder (warped_dst)
            pred_src_src = self.decoder_src(warped_src_code)
            pred_dst_dst = self.decoder_dst(warped_dst_code)
            pred_src_dst = self.decoder_src(warped_dst_code)

            if self.options['learn_mask']:
                pred_src_srcm = self.decoder_srcm(warped_src_code)
                pred_dst_dstm = self.decoder_dstm(warped_dst_code)
                pred_src_dstm = self.decoder_srcm(warped_dst_code)

        if self.is_first_run():
            if self.options.get('ca_weights',False):
                conv_weights_list = []
                for model in models_list:
                    for layer in model.layers:
                        if type(layer) == keras.layers.Conv2D:
                            conv_weights_list += [layer.weights[0]] #Conv2D kernel_weights
                CAInitializerMP ( conv_weights_list )
        else:
            self.load_weights_safe(weights_to_load)

        pred_src_src, pred_dst_dst, pred_src_dst, = [ [x] if type(x) != list else x for x in [pred_src_src, pred_dst_dst, pred_src_dst, ] ]

        if self.options['learn_mask']:
            pred_src_srcm, pred_dst_dstm, pred_src_dstm = [ [x] if type(x) != list else x for x in [pred_src_srcm, pred_dst_dstm, pred_src_dstm] ]

        target_srcm_blurred_ar = [ gaussian_blur( max(1, K.int_shape(x)[1] // 32) )(x) for x in target_srcm_ar]
        target_srcm_sigm_ar = target_srcm_blurred_ar #[ x / 2.0 + 0.5 for x in target_srcm_blurred_ar]
        target_srcm_anti_sigm_ar = [ 1.0 - x for x in target_srcm_sigm_ar]

        target_dstm_blurred_ar = [ gaussian_blur( max(1, K.int_shape(x)[1] // 32) )(x) for x in target_dstm_ar]
        target_dstm_sigm_ar = target_dstm_blurred_ar#[ x / 2.0 + 0.5 for x in target_dstm_blurred_ar]
        target_dstm_anti_sigm_ar = [ 1.0 - x for x in target_dstm_sigm_ar]

        target_src_sigm_ar = target_src_ar#[ x + 1 for x in target_src_ar]
        target_dst_sigm_ar = target_dst_ar#[ x + 1 for x in target_dst_ar]

        pred_src_src_sigm_ar = pred_src_src#[ x + 1 for x in pred_src_src]
        pred_dst_dst_sigm_ar = pred_dst_dst#[ x + 1 for x in pred_dst_dst]
        pred_src_dst_sigm_ar = pred_src_dst#[ x + 1 for x in pred_src_dst]

        target_src_masked_ar = [ target_src_sigm_ar[i]*target_srcm_sigm_ar[i]  for i in range(len(target_src_sigm_ar))]
        target_dst_masked_ar = [ target_dst_sigm_ar[i]*target_dstm_sigm_ar[i]  for i in range(len(target_dst_sigm_ar))]
        target_dst_anti_masked_ar = [ target_dst_sigm_ar[i]*target_dstm_anti_sigm_ar[i]  for i in range(len(target_dst_sigm_ar))]

        pred_src_src_masked_ar = [ pred_src_src_sigm_ar[i] * target_srcm_sigm_ar[i]  for i in range(len(pred_src_src_sigm_ar))]
        pred_dst_dst_masked_ar = [ pred_dst_dst_sigm_ar[i] * target_dstm_sigm_ar[i]  for i in range(len(pred_dst_dst_sigm_ar))]

        target_src_masked_ar_opt = target_src_masked_ar if masked_training else target_src_sigm_ar
        target_dst_masked_ar_opt = target_dst_masked_ar if masked_training else target_dst_sigm_ar

        pred_src_src_masked_ar_opt = pred_src_src_masked_ar if masked_training else pred_src_src_sigm_ar
        pred_dst_dst_masked_ar_opt = pred_dst_dst_masked_ar if masked_training else pred_dst_dst_sigm_ar

        psd_target_dst_masked_ar = [ pred_src_dst_sigm_ar[i]*target_dstm_sigm_ar[i]  for i in range(len(pred_src_dst_sigm_ar))]
        psd_target_dst_anti_masked_ar = [ pred_src_dst_sigm_ar[i]*target_dstm_anti_sigm_ar[i]  for i in range(len(pred_src_dst_sigm_ar))]

        if self.is_training_mode:
            self.src_dst_opt      = Adam(lr=5e-5, beta_1=0.5, beta_2=0.999, tf_cpu_mode=self.options['optimizer_mode']-1)
            self.src_dst_mask_opt = Adam(lr=5e-5, beta_1=0.5, beta_2=0.999, tf_cpu_mode=self.options['optimizer_mode']-1)

            if 'liae' in self.options['archi']:
                src_dst_loss_train_weights = self.encoder.trainable_weights + self.inter_B.trainable_weights + self.inter_AB.trainable_weights + self.decoder.trainable_weights
                if self.options['learn_mask']:
                    src_dst_mask_loss_train_weights = self.encoder.trainable_weights + self.inter_B.trainable_weights + self.inter_AB.trainable_weights + self.decoderm.trainable_weights
            else:
                src_dst_loss_train_weights = self.encoder.trainable_weights + self.decoder_src.trainable_weights + self.decoder_dst.trainable_weights
                if self.options['learn_mask']:
                    src_dst_mask_loss_train_weights = self.encoder.trainable_weights + self.decoder_srcm.trainable_weights + self.decoder_dstm.trainable_weights

            if not self.options['pixel_loss']:
                src_loss_batch = sum([ 10*dssim(kernel_size=int(resolution/11.6),max_value=1.0)( target_src_masked_ar_opt[i], pred_src_src_masked_ar_opt[i])  for i in range(len(target_src_masked_ar_opt)) ])
            else:
                src_loss_batch = sum([ K.mean ( 50*K.square( target_src_masked_ar_opt[i] - pred_src_src_masked_ar_opt[i] ), axis=[1,2,3]) for i in range(len(target_src_masked_ar_opt)) ])

            src_loss = K.mean(src_loss_batch)

            face_style_power = self.options['face_style_power']  / 100.0

            if face_style_power != 0:
                src_loss += style_loss(gaussian_blur_radius=resolution//16, loss_weight=face_style_power, wnd_size=0)( psd_target_dst_masked_ar[-1], target_dst_masked_ar[-1] )

            bg_style_power = self.options['bg_style_power'] / 100.0
            if bg_style_power != 0:
                if not self.options['pixel_loss']:
                    bg_loss = K.mean( (10*bg_style_power)*dssim(kernel_size=int(resolution/11.6),max_value=1.0)( psd_target_dst_anti_masked_ar[-1], target_dst_anti_masked_ar[-1] ))
                else:
                    bg_loss = K.mean( (50*bg_style_power)*K.square( psd_target_dst_anti_masked_ar[-1] - target_dst_anti_masked_ar[-1] ))
                src_loss += bg_loss

            if not self.options['pixel_loss']:
                dst_loss_batch = sum([ 10*dssim(kernel_size=int(resolution/11.6),max_value=1.0)(target_dst_masked_ar_opt[i], pred_dst_dst_masked_ar_opt[i]) for i in range(len(target_dst_masked_ar_opt)) ])
            else:
                dst_loss_batch = sum([ K.mean ( 50*K.square( target_dst_masked_ar_opt[i] - pred_dst_dst_masked_ar_opt[i] ), axis=[1,2,3]) for i in range(len(target_dst_masked_ar_opt)) ])

            dst_loss = K.mean(dst_loss_batch)

            feed = [warped_src, warped_dst]
            feed += target_src_ar[::-1]
            feed += target_srcm_ar[::-1]
            feed += target_dst_ar[::-1]
            feed += target_dstm_ar[::-1]

            self.src_dst_train = K.function (feed,[src_loss,dst_loss], self.src_dst_opt.get_updates(src_loss+dst_loss, src_dst_loss_train_weights) )

            if self.options['learn_mask']:
                src_mask_loss = sum([ K.mean(K.square(target_srcm_ar[-1]-pred_src_srcm[-1])) for i in range(len(target_srcm_ar)) ])
                dst_mask_loss = sum([ K.mean(K.square(target_dstm_ar[-1]-pred_dst_dstm[-1])) for i in range(len(target_dstm_ar)) ])

                feed = [ warped_src, warped_dst]
                feed += target_srcm_ar[::-1]
                feed += target_dstm_ar[::-1]

                self.src_dst_mask_train = K.function (feed,[src_mask_loss, dst_mask_loss], self.src_dst_mask_opt.get_updates(src_mask_loss+dst_mask_loss, src_dst_mask_loss_train_weights) )

            if self.options['learn_mask']:
                self.AE_view = K.function ([warped_src, warped_dst], [pred_src_src[-1], pred_dst_dst[-1], pred_dst_dstm[-1], pred_src_dst[-1], pred_src_dstm[-1]])
            else:
                self.AE_view = K.function ([warped_src, warped_dst], [pred_src_src[-1], pred_dst_dst[-1], pred_src_dst[-1] ] )


        else:
            if self.options['learn_mask']:
                self.AE_convert = K.function ([warped_dst],[ pred_src_dst[-1], pred_dst_dstm[-1], pred_src_dstm[-1] ])
            else:
                self.AE_convert = K.function ([warped_dst],[ pred_src_dst[-1] ])


        if self.is_training_mode:
            self.src_sample_losses = []
            self.dst_sample_losses = []

            t = SampleProcessor.Types
            face_type = t.FACE_TYPE_FULL if self.options['face_type'] == 'f' else t.FACE_TYPE_HALF

            t_mode_bgr = t.MODE_BGR if not self.pretrain else t.MODE_BGR_SHUFFLE

            training_data_src_path = self.training_data_src_path
            training_data_dst_path = self.training_data_dst_path
            sort_by_yaw = self.sort_by_yaw

            if self.pretrain and self.pretraining_data_path is not None:
                training_data_src_path = self.pretraining_data_path
                training_data_dst_path = self.pretraining_data_path
                sort_by_yaw = False

            self.set_training_data_generators ([
                    SampleGeneratorFace(training_data_src_path, sort_by_yaw_target_samples_path=training_data_dst_path if sort_by_yaw else None,
                                                                random_ct_samples_path=training_data_dst_path if apply_random_ct else None,
                                                                debug=self.is_debug(), batch_size=self.batch_size,
                        sample_process_options=SampleProcessor.Options(random_flip=self.random_flip, scale_range=np.array([-0.05, 0.05])+self.src_scale_mod / 100.0 ),
                        output_sample_types = [ {'types' : (t.IMG_WARPED_TRANSFORMED, face_type, t_mode_bgr), 'resolution':resolution, 'apply_ct': apply_random_ct} ] + \
                                              [ {'types' : (t.IMG_TRANSFORMED, face_type, t_mode_bgr), 'resolution': resolution // (2**i), 'apply_ct': apply_random_ct } for i in range(ms_count)] + \
                                              [ {'types' : (t.IMG_TRANSFORMED, face_type, t.MODE_M), 'resolution': resolution // (2**i) } for i in range(ms_count)]
                         ),

                    SampleGeneratorFace(training_data_dst_path, debug=self.is_debug(), batch_size=self.batch_size,
                        sample_process_options=SampleProcessor.Options(random_flip=self.random_flip, ),
                        output_sample_types = [ {'types' : (t.IMG_WARPED_TRANSFORMED, face_type, t_mode_bgr), 'resolution':resolution} ] + \
                                              [ {'types' : (t.IMG_TRANSFORMED, face_type, t_mode_bgr), 'resolution': resolution // (2**i)} for i in range(ms_count)] + \
                                              [ {'types' : (t.IMG_TRANSFORMED, face_type, t.MODE_M), 'resolution': resolution // (2**i) } for i in range(ms_count)])
                    ])

    #override
    def onSave(self):
        opt_ar = [ [self.src_dst_opt,      'src_dst_opt'],
                   [self.src_dst_mask_opt, 'src_dst_mask_opt']
                 ]
        ar = []
        if 'liae' in self.options['archi']:
            ar += [[self.encoder, 'encoder.h5'],
                   [self.inter_B, 'inter_B.h5'],
                   [self.decoder, 'decoder.h5']
                  ]

            if not self.pretrain or self.iter == 0:
                ar += [ [self.inter_AB, 'inter_AB.h5'],
                      ]

            if self.options['learn_mask']:
                 ar += [ [self.decoderm, 'decoderm.h5'] ]

        elif 'df' in self.options['archi']:
            if not self.pretrain or self.iter == 0:
                ar += [ [self.encoder, 'encoder.h5'],
                      ]

            ar += [ [self.decoder_src, 'decoder_src.h5'],
                    [self.decoder_dst, 'decoder_dst.h5']
                  ]

            if self.options['learn_mask']:
                ar += [ [self.decoder_srcm, 'decoder_srcm.h5'],
                        [self.decoder_dstm, 'decoder_dstm.h5'] ]

        self.save_weights_safe(ar)


    #override
    def onTrainOneIter(self, generators_samples, generators_list):
        src_samples  = generators_samples[0]
        dst_samples  = generators_samples[1]

        feed = [src_samples[0], dst_samples[0] ] + \
                src_samples[1:1+self.ms_count*2] + \
                dst_samples[1:1+self.ms_count*2]

        src_loss, dst_loss, = self.src_dst_train (feed)

        if self.options['learn_mask']:
            feed = [ src_samples[0], dst_samples[0] ] + \
                   src_samples[1+self.ms_count:1+self.ms_count*2] + \
                   dst_samples[1+self.ms_count:1+self.ms_count*2]
            src_mask_loss, dst_mask_loss, = self.src_dst_mask_train (feed)

        return ( ('src_loss', src_loss), ('dst_loss', dst_loss) )


    #override
    def onGetPreview(self, sample):
        test_S   = sample[0][1][0:4] #first 4 samples
        test_S_m = sample[0][1+self.ms_count][0:4] #first 4 samples
        test_D   = sample[1][1][0:4]
        test_D_m = sample[1][1+self.ms_count][0:4]

        if self.options['learn_mask']:
            S, D, SS, DD, DDM, SD, SDM = [ np.clip(x, 0.0, 1.0) for x in ([test_S,test_D] + self.AE_view ([test_S, test_D]) ) ]
            DDM, SDM, = [ np.repeat (x, (3,), -1) for x in [DDM, SDM] ]
        else:
            S, D, SS, DD, SD, = [ np.clip(x, 0.0, 1.0) for x in ([test_S,test_D] + self.AE_view ([test_S, test_D]) ) ]

        result = []
        st = []
        for i in range(0, len(test_S)):
            ar = S[i], SS[i], D[i], DD[i], SD[i]
            st.append ( np.concatenate ( ar, axis=1) )

        result += [ ('SAE', np.concatenate (st, axis=0 )), ]

        if self.options['learn_mask']:
            st_m = []
            for i in range(0, len(test_S)):
                ar = S[i]*test_S_m[i], SS[i], D[i]*test_D_m[i], DD[i]*DDM[i], SD[i]*(DDM[i]*SDM[i])
                st_m.append ( np.concatenate ( ar, axis=1) )

            result += [ ('SAE masked', np.concatenate (st_m, axis=0 )), ]

        return result

    def predictor_func (self, face):
        if self.options['learn_mask']:
            bgr, mask_dst_dstm, mask_src_dstm = self.AE_convert ([face[np.newaxis,...]])
            mask = mask_dst_dstm[0] * mask_src_dstm[0]
            return bgr[0], mask[...,0]
        else:
            bgr, = self.AE_convert ([face[np.newaxis,...]])
            return bgr[0]

    #override
    def get_converter(self):
        base_erode_mask_modifier = 30 if self.options['face_type'] == 'f' else 100
        base_blur_mask_modifier = 0 if self.options['face_type'] == 'f' else 100

        default_erode_mask_modifier = 0
        default_blur_mask_modifier = 100 if (self.options['face_style_power'] or self.options['bg_style_power']) and \
                                                self.options['face_type'] == 'f' else 0

        face_type = FaceType.FULL if self.options['face_type'] == 'f' else FaceType.HALF

        from converters import ConverterMasked
        return ConverterMasked(self.predictor_func,
                               predictor_input_size=self.options['resolution'],
                               predictor_masked=self.options['learn_mask'],
                               face_type=face_type,
                               default_mode = 1 if self.options['face_style_power'] or self.options['bg_style_power'] else 4,
                               base_erode_mask_modifier=base_erode_mask_modifier,
                               base_blur_mask_modifier=base_blur_mask_modifier,
                               default_erode_mask_modifier=default_erode_mask_modifier,
                               default_blur_mask_modifier=default_blur_mask_modifier,
                               clip_hborder_mask_per=0.0625 if (self.options['face_type'] == 'f') else 0)

    @staticmethod
    def initialize_nn_functions():
        exec (nnlib.import_all(), locals(), globals())

        def NormPass(x):
            return x

        def Norm(norm=''):
            if norm == 'bn':
                return BatchNormalization(axis=-1)
            else:
                return NormPass

        def Act(act='', lrelu_alpha=0.1):
            if act == 'prelu':
                return PReLU()
            else:
                return LeakyReLU(alpha=lrelu_alpha)

        class ResidualBlock(object):
            def __init__(self, filters, kernel_size=3, padding='zero', norm='', act='', **kwargs):
                self.filters = filters
                self.kernel_size = kernel_size
                self.padding = padding
                self.norm = norm
                self.act = act

            def __call__(self, inp):
                x = inp
                x = Conv2D(self.filters, kernel_size=self.kernel_size, padding=self.padding)(x)
                x = Act(self.act, lrelu_alpha=0.2)(x)
                x = Norm(self.norm)(x)
                x = Conv2D(self.filters, kernel_size=self.kernel_size, padding=self.padding)(x)
                x = Add()([x, inp])
                x = Act(self.act, lrelu_alpha=0.2)(x)
                x = Norm(self.norm)(x)
                return x
        SAEModel.ResidualBlock = ResidualBlock

        def downscale (dim, padding='zero', norm='', act='', **kwargs):
            def func(x):
                return Norm(norm)( Act(act) (Conv2D(dim, kernel_size=5, strides=2, padding=padding)(x)) )
            return func
        SAEModel.downscale = downscale

        def upscale (dim, padding='zero', norm='', act='', **kwargs):
            def func(x):
                return SubpixelUpscaler()(Norm(norm)(Act(act)(Conv2D(dim * 4, kernel_size=3, strides=1, padding=padding)(x))))
            return func
        SAEModel.upscale = upscale

        def to_bgr (output_nc, padding='zero', **kwargs):
            def func(x):
                return Conv2D(output_nc, kernel_size=5, padding=padding, activation='sigmoid')(x)
            return func
        SAEModel.to_bgr = to_bgr

    @staticmethod
    def LIAEEncFlow(resolution, ch_dims, **kwargs):
        exec (nnlib.import_all(), locals(), globals())
        upscale = partial(SAEModel.upscale, **kwargs)
        downscale = partial(SAEModel.downscale, **kwargs)

        def func(input):
            dims = K.int_shape(input)[-1]*ch_dims

            x = input
            x = downscale(dims)(x)
            x = downscale(dims*2)(x)
            x = downscale(dims*4)(x)
            x = downscale(dims*8)(x)

            x = Flatten()(x)
            return x
        return func

    @staticmethod
    def LIAEInterFlow(resolution, ae_dims=256, **kwargs):
        exec (nnlib.import_all(), locals(), globals())
        upscale = partial(SAEModel.upscale, **kwargs)
        lowest_dense_res=resolution // 16

        def func(input):
            x = input[0]
            x = Dense(ae_dims)(x)
            x = Dense(lowest_dense_res * lowest_dense_res * ae_dims*2)(x)
            x = Reshape((lowest_dense_res, lowest_dense_res, ae_dims*2))(x)
            x = upscale(ae_dims*2)(x)
            return x
        return func

    @staticmethod
    def LIAEDecFlow(output_nc,ch_dims, multiscale_count=1, add_residual_blocks=False, **kwargs):
        exec (nnlib.import_all(), locals(), globals())
        upscale = partial(SAEModel.upscale, **kwargs)
        to_bgr = partial(SAEModel.to_bgr, **kwargs)
        dims = output_nc * ch_dims
        ResidualBlock = partial(SAEModel.ResidualBlock, **kwargs)

        def func(input):
            x = input[0]

            outputs = []
            x1  = upscale(dims*8)( x )

            if add_residual_blocks:
                x1 = ResidualBlock(dims*8)(x1)
                x1 = ResidualBlock(dims*8)(x1)

            if multiscale_count >= 3:
                outputs += [ to_bgr(output_nc) ( x1 ) ]

            x2 = upscale(dims*4)( x1 )

            if add_residual_blocks:
                x2 = ResidualBlock(dims*4)(x2)
                x2 = ResidualBlock(dims*4)(x2)

            if multiscale_count >= 2:
                outputs += [ to_bgr(output_nc) ( x2 ) ]

            x3 = upscale(dims*2)( x2 )

            if add_residual_blocks:
                x3 = ResidualBlock( dims*2)(x3)
                x3 = ResidualBlock( dims*2)(x3)

            outputs += [ to_bgr(output_nc) ( x3 ) ]

            return outputs
        return func

    @staticmethod
    def DFEncFlow(resolution, ae_dims, ch_dims, **kwargs):
        exec (nnlib.import_all(), locals(), globals())
        upscale = partial(SAEModel.upscale, **kwargs)
        downscale = partial(SAEModel.downscale, **kwargs)#, kernel_regularizer=keras.regularizers.l2(0.0),
        lowest_dense_res = resolution // 16

        def func(input):
            x = input

            dims = K.int_shape(input)[-1]*ch_dims
            x = downscale(dims)(x)
            x = downscale(dims*2)(x)
            x = downscale(dims*4)(x)
            x = downscale(dims*8)(x)

            x = Dense(ae_dims)(Flatten()(x))
            x = Dense(lowest_dense_res * lowest_dense_res * ae_dims)(x)
            x = Reshape((lowest_dense_res, lowest_dense_res, ae_dims))(x)
            x = upscale(ae_dims)(x)
            return x
        return func

    @staticmethod
    def DFDecFlow(output_nc, ch_dims, multiscale_count=1, add_residual_blocks=False, **kwargs):
        exec (nnlib.import_all(), locals(), globals())
        upscale = partial(SAEModel.upscale, **kwargs)
        to_bgr = partial(SAEModel.to_bgr, **kwargs)
        dims = output_nc * ch_dims
        ResidualBlock = partial(SAEModel.ResidualBlock, **kwargs)

        def func(input):
            x = input[0]

            outputs = []
            x1 = upscale(dims*8)( x )

            if add_residual_blocks:
                x1 = ResidualBlock( dims*8 )(x1)
                x1 = ResidualBlock( dims*8 )(x1)

            if multiscale_count >= 3:
                outputs += [ to_bgr(output_nc) ( x1 ) ]

            x2 = upscale(dims*4)( x1 )

            if add_residual_blocks:
                x2 = ResidualBlock( dims*4)(x2)
                x2 = ResidualBlock( dims*4)(x2)

            if multiscale_count >= 2:
                outputs += [ to_bgr(output_nc) ( x2 ) ]

            x3 = upscale(dims*2)( x2 )

            if add_residual_blocks:
                x3 = ResidualBlock( dims*2)(x3)
                x3 = ResidualBlock( dims*2)(x3)

            outputs += [ to_bgr(output_nc) ( x3 ) ]

            return outputs
        return func


Model = SAEModel