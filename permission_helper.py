#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android权限辅助模块
用于处理Android应用的各种权限请求
"""

import os
import sys
from threading import Lock

# Android相关导入
try:
    from android.permissions import (
        request_permissions,
        Permission,
        check_permission
    )
    ANDROID_AVAILABLE = True
except ImportError:
    ANDROID_AVAILABLE = False
    print("警告: 未检测到Android环境，权限模块将以模拟模式运行")

try:
    from android.storage import primary_external_storage_path
    ANDROID_STORAGE_AVAILABLE = True
except ImportError:
    ANDROID_STORAGE_AVAILABLE = False


class PermissionHelper:
    """权限辅助类"""
    
    # 权限类型定义
    STORAGE_WRITE = 'storage_write'
    STORAGE_READ = 'storage_read'
    INTERNET = 'internet'
    STORAGE_MANAGE = 'storage_manage'
    
    # 权限状态
    PERMISSION_GRANTED = 'granted'
    PERMISSION_DENIED = 'denied'
    PERMISSION_PERMANENTLY_DENIED = 'permanently_denied'
    PERMISSION_NOT_REQUESTED = 'not_requested'
    PERMISSION_NOT_AVAILABLE = 'not_available'
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(PermissionHelper, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化权限辅助类"""
        if self._initialized:
            return
        
        self._initialized = True
        self._permission_callbacks = {}
        self._permission_status = {}
        
        # 初始化权限状态
        self._initialize_permission_status()
    
    def _initialize_permission_status(self):
        """初始化所有权限的状态"""
        permissions = [
            self.STORAGE_WRITE,
            self.STORAGE_READ,
            self.INTERNET,
            self.STORAGE_MANAGE
        ]
        
        for perm in permissions:
            if not ANDROID_AVAILABLE:
                self._permission_status[perm] = self.PERMISSION_NOT_AVAILABLE
            else:
                self._permission_status[perm] = self.PERMISSION_NOT_REQUESTED
    
    def is_android(self):
        """检查是否运行在Android环境"""
        return ANDROID_AVAILABLE
    
    def get_storage_path(self):
        """获取Android外部存储路径"""
        if ANDROID_STORAGE_AVAILABLE:
            return primary_external_storage_path()
        else:
            # 非Android环境返回当前目录
            return os.getcwd()
    
    def check_permission_status(self, permission_type):
        """
        检查指定权限的状态
        
        参数:
            permission_type: 权限类型，使用类中定义的常量
            
        返回:
            权限状态字符串
        """
        if not ANDROID_AVAILABLE:
            return self.PERMISSION_NOT_AVAILABLE
        
        try:
            # 映射权限类型到Android权限
            android_permission = self._get_android_permission(permission_type)
            
            # 检查权限
            if check_permission(android_permission):
                self._permission_status[permission_type] = self.PERMISSION_GRANTED
                return self.PERMISSION_GRANTED
            else:
                return self._permission_status.get(permission_type, self.PERMISSION_NOT_REQUESTED)
        except Exception as e:
            print(f"检查权限时出错: {str(e)}")
            return self.PERMISSION_NOT_AVAILABLE
    
    def _get_android_permission(self, permission_type):
        """
        将内部权限类型映射到Android权限对象
        
        参数:
            permission_type: 内部权限类型
            
        返回:
            Android权限对象
        """
        permission_map = {
            self.STORAGE_WRITE: Permission.WRITE_EXTERNAL_STORAGE,
            self.STORAGE_READ: Permission.READ_EXTERNAL_STORAGE,
            self.INTERNET: Permission.INTERNET,
            self.STORAGE_MANAGE: Permission.MANAGE_EXTERNAL_STORAGE
        }
        
        return permission_map.get(permission_type, None)
    
    def request_permission(self, permission_type, callback=None):
        """
        请求指定权限
        
        参数:
            permission_type: 权限类型，使用类中定义的常量
            callback: 权限回调函数，接收权限类型和状态作为参数
            
        返回:
            True表示已请求权限，False表示请求失败
        """
        if not ANDROID_AVAILABLE:
            print(f"非Android环境，跳过权限请求: {permission_type}")
            if callback:
                callback(permission_type, self.PERMISSION_NOT_AVAILABLE)
            return False
        
        try:
            android_permission = self._get_android_permission(permission_type)
            if android_permission is None:
                print(f"未知的权限类型: {permission_type}")
                return False
            
            # 保存回调函数
            if callback:
                self._permission_callbacks[permission_type] = callback
            
            # 请求权限
            request_permissions([android_permission], self._permission_callback)
            self._permission_status[permission_type] = self.PERMISSION_NOT_REQUESTED
            return True
            
        except Exception as e:
            print(f"请求权限时出错: {str(e)}")
            if callback:
                callback(permission_type, self.PERMISSION_DENIED)
            return False
    
    def request_all_permissions(self, callback=None):
        """
        请求所有必要的权限
        
        参数:
            callback: 所有权限请求完成后的回调函数，接收权限状态字典作为参数
            
        返回:
            True表示已开始请求所有权限，False表示请求失败
        """
        if not ANDROID_AVAILABLE:
            print("非Android环境，跳过权限请求")
            if callback:
                status = {perm: self.PERMISSION_NOT_AVAILABLE for perm in [
                    self.STORAGE_WRITE, self.STORAGE_READ, self.INTERNET, self.STORAGE_MANAGE
                ]}
                callback(status)
            return False
        
        permissions_needed = [
            self.STORAGE_WRITE,
            self.STORAGE_READ,
            self.INTERNET,
            self.STORAGE_MANAGE
        ]
        
        all_permissions = []
        for perm_type in permissions_needed:
            android_perm = self._get_android_permission(perm_type)
            if android_perm:
                all_permissions.append(android_perm)
        
        try:
            # 请求所有权限
            request_permissions(all_permissions, lambda permissions, grants: self._all_permissions_callback(permissions, grants, callback))
            
            # 更新权限状态
            for perm_type in permissions_needed:
                self._permission_status[perm_type] = self.PERMISSION_NOT_REQUESTED
                
            return True
            
        except Exception as e:
            print(f"请求所有权限时出错: {str(e)}")
            if callback:
                status = {perm: self.PERMISSION_DENIED for perm in permissions_needed}
                callback(status)
            return False
    
    def _permission_callback(self, permissions, grants):
        """
        单个权限请求的回调函数
        
        参数:
            permissions: 请求的权限列表
            grants: 权限授予结果列表
        """
        if len(permissions) != len(grants):
            print("权限回调数据不匹配")
            return
        
        for i, perm in enumerate(permissions):
            granted = grants[i]
            
            # 找到对应的内部权限类型
            permission_type = None
            for key, value in {
                self.STORAGE_WRITE: Permission.WRITE_EXTERNAL_STORAGE,
                self.STORAGE_READ: Permission.READ_EXTERNAL_STORAGE,
                self.INTERNET: Permission.INTERNET,
                self.STORAGE_MANAGE: Permission.MANAGE_EXTERNAL_STORAGE
            }.items():
                if perm == value:
                    permission_type = key
                    break
            
            if permission_type:
                # 更新权限状态
                if granted:
                    self._permission_status[permission_type] = self.PERMISSION_GRANTED
                else:
                    self._permission_status[permission_type] = self.PERMISSION_DENIED
                
                # 调用用户回调
                if permission_type in self._permission_callbacks:
                    callback = self._permission_callbacks[permission_type]
                    callback(permission_type, self._permission_status[permission_type])
    
    def _all_permissions_callback(self, permissions, grants, global_callback):
        """
        所有权限请求完成的回调函数
        
        参数:
            permissions: 请求的权限列表
            grants: 权限授予结果列表
            global_callback: 全局回调函数
        """
        if len(permissions) != len(grants):
            print("权限回调数据不匹配")
            return
        
        status = {}
        
        for i, perm in enumerate(permissions):
            granted = grants[i]
            
            # 找到对应的内部权限类型
            permission_type = None
            for key, value in {
                self.STORAGE_WRITE: Permission.WRITE_EXTERNAL_STORAGE,
                self.STORAGE_READ: Permission.READ_EXTERNAL_STORAGE,
                self.INTERNET: Permission.INTERNET,
                self.STORAGE_MANAGE: Permission.MANAGE_EXTERNAL_STORAGE
            }.items():
                if perm == value:
                    permission_type = key
                    break
            
            if permission_type:
                # 更新权限状态
                if granted:
                    self._permission_status[permission_type] = self.PERMISSION_GRANTED
                else:
                    self._permission_status[permission_type] = self.PERMISSION_DENIED
                
                status[permission_type] = self._permission_status[permission_type]
        
        # 调用全局回调
        if global_callback:
            global_callback(status)
    
    def ensure_storage_permissions(self, callback=None):
        """
        确保拥有存储权限，如果没有则请求
        
        参数:
            callback: 权限状态回调函数
            
        返回:
            如果已有权限返回True，否则返回False并开始请求
        """
        # 检查Android 11+的存储权限
        api_level = self._get_android_api_level()
        
        if api_level >= 30:  # Android 11+
            # 优先检查MANAGE_EXTERNAL_STORAGE权限
            manage_status = self.check_permission_status(self.STORAGE_MANAGE)
            if manage_status == self.PERMISSION_GRANTED:
                return True
            
            # 如果没有MANAGE_EXTERNAL_STORAGE，检查普通存储权限
            write_status = self.check_permission_status(self.STORAGE_WRITE)
            if write_status == self.PERMISSION_GRANTED:
                return True
        else:
            # Android 11以下，检查普通存储权限
            write_status = self.check_permission_status(self.STORAGE_WRITE)
            if write_status == self.PERMISSION_GRANTED:
                return True
        
        # 没有权限，开始请求
        self.request_all_permissions(callback)
        return False
    
    def _get_android_api_level(self):
        """获取Android API级别"""
        if not ANDROID_AVAILABLE:
            return 0
        
        try:
            from jnius import autoclass
            Build_VERSION = autoclass('android.os.Build$VERSION')
            return Build_VERSION.SDK_INT
        except:
            return 0
    
    def get_permissions_status(self):
        """
        获取所有权限的当前状态
        
        返回:
            包含所有权限状态的字典
        """
        return self._permission_status.copy()
    
    def has_required_permissions(self):
        """
        检查是否拥有所有必需的权限
        
        返回:
            如果拥有所有必需权限返回True，否则返回False
        """
        if not ANDROID_AVAILABLE:
            return True  # 非Android环境不需要权限
        
        api_level = self._get_android_api_level()
        
        if api_level >= 30:  # Android 11+
            # 需要MANAGE_EXTERNAL_STORAGE或普通存储权限
            manage = self.check_permission_status(self.STORAGE_MANAGE)
            write = self.check_permission_status(self.STORAGE_WRITE)
            return manage == self.PERMISSION_GRANTED or write == self.PERMISSION_GRANTED
        else:
            # 只需要普通存储权限
            write = self.check_permission_status(self.STORAGE_WRITE)
            return write == self.PERMISSION_GRANTED
    
    def can_write_to_storage(self):
        """
        检查是否可以写入存储
        
        返回:
            如果可以写入返回True，否则返回False
        """
        if not ANDROID_AVAILABLE:
            return True  # 非Android环境可以直接写入
        
        return self.has_required_permissions()
    
    def get_safe_storage_path(self, subpath=""):
        """
        获取安全的存储路径，考虑权限情况
        
        参数:
            subpath: 相对路径，可以是空字符串
            
        返回:
            安全的存储路径
        """
        if not ANDROID_AVAILABLE:
            # 非Android环境
            base_path = os.getcwd()
        else:
            # Android环境
            if self.has_required_permissions():
                base_path = self.get_storage_path()
            else:
                # 没有权限，使用应用私有目录
                try:
                    from jnius import autoclass
                    Context = autoclass('android.content.Context')
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    activity = PythonActivity.mActivity
                    base_path = activity.getFilesDir().getAbsolutePath()
                except:
                    base_path = os.getcwd()
        
        # 添加子路径
        if subpath:
            safe_path = os.path.join(base_path, subpath)
        else:
            safe_path = base_path
        
        # 确保路径存在
        try:
            os.makedirs(safe_path, exist_ok=True)
        except:
            pass
        
        return safe_path


# 创建单例实例
permission_helper = PermissionHelper()


def ensure_app_permissions(callback=None):
    """
    确保应用拥有所有必要权限的便捷函数
    
    参数:
        callback: 权限状态回调函数
        
    返回:
        如果已有权限返回True，否则返回False并开始请求
    """
    return permission_helper.ensure_storage_permissions(callback)


def has_write_permission():
    """
    检查是否有写入权限的便捷函数
    
    返回:
        如果有写入权限返回True，否则返回False
    """
    return permission_helper.can_write_to_storage()


def get_app_storage_path(subpath=""):
    """
    获取应用存储路径的便捷函数
    
    参数:
        subpath: 相对路径
        
    返回:
        安全的存储路径
    """
    return permission_helper.get_safe_storage_path(subpath)