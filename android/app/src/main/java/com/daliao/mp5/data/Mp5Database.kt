package com.daliao.mp5.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

/**
 * MP5 Room数据库
 *
 * @author 大米斗（Aniseedaliao）
 */
@Database(entities = [Mp5FileEntity::class], version = 1, exportSchema = false)
abstract class Mp5Database : RoomDatabase() {
    abstract fun mp5FileDao(): Mp5FileDao

    companion object {
        @Volatile
        private var INSTANCE: Mp5Database? = null

        fun getInstance(context: Context): Mp5Database {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    Mp5Database::class.java,
                    "mp5_database"
                ).fallbackToDestructiveMigration().build().also { INSTANCE = it }
            }
        }
    }
}