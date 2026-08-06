package com.daliao.mp5.data

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface Mp5FileDao {

    @Query("SELECT * FROM mp5_files ORDER BY createdAt DESC")
    fun getAllFiles(): Flow<List<Mp5FileEntity>>

    @Query("SELECT * FROM mp5_files WHERE id = :id")
    suspend fun getFileById(id: Long): Mp5FileEntity?

    @Insert
    suspend fun insert(file: Mp5FileEntity): Long

    @Update
    suspend fun update(file: Mp5FileEntity)

    @Delete
    suspend fun delete(file: Mp5FileEntity)

    @Query("DELETE FROM mp5_files WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("SELECT COUNT(*) FROM mp5_files")
    suspend fun getCount(): Int
}